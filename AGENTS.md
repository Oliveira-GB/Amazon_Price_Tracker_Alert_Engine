# AGENTS.md - Agent & Worker Architecture

## 0. Document Versioning and Evolution
<!-- This is a living document. Update agent statuses and rules as the project advances. -->
* **Version:** 0.4
* **Last Updated:** September 6, 2026
* **Overall Project Status:** Planning / Design

### 0.1. Architectural Decision Records (ADR / Changelog)
<!-- Record major direction changes and the REASON why they occurred here. -->
* **[09/06/2026] - v0.4:** Added Graceful Shutdown rules, Consumer Idempotency, and Strict Data Contracts (Pydantic) to prepare for the start of development.
* **[09/06/2026] - v0.3:** Adopted Monorepo pattern to simplify deployment. Included QoS (Prefetch Count) requirement in RabbitMQ for load balancing, use of Alembic for migrations, and definition of Docker Compose for the local environment.
* **[09/06/2026] - v0.2:** Centralized all outputs to Telegram exclusively in the `Notification Worker` to respect the Single Responsibility Principle (SRP). Included strict Timeout and Circuit Breaker rules to prevent workers from freezing on network calls.

### 0.2. Technical Debts and Assumed Risks (Known Tech Debts)
<!-- List what was done in a simplified way in the MVP and will require future refactoring. -->
* **Anti-Bot Evasion:** We currently rely only on Jitter and User-Agent rotation. If Amazon applies blocks by native Cloud IP, we will have to plan the introduction of Residential Proxies.
* **DLQ Management:** Currently, messages in the DLQ require manual inspection via the RabbitMQ dashboard. A dedicated dashboard/CLI for mass reprocessing is missing.

---

## 1. Overview
The **Amazon Price Tracker & Alert Engine** adopts a distributed architecture based on **asynchronous, event-driven Micro-Workers (Event-Driven Architecture)**. 

To ensure scalability, resilience against Amazon's anti-bot blocks, and maintenance of strictly zeroed costs (Free Tiers), the system components **do not communicate directly via synchronous HTTP requests**. The entire data flow — from receiving a link on Telegram, through periodic price scanning, to decision-making and alert triggering — is intermediated and decoupled through a *Message Broker* (RabbitMQ).

Built mostly in **Python (3.11+)** using asynchronous libraries (`aio-pika`, `httpx`, `asyncpg`), this model ensures that the isolated failure of a component (e.g., a scraper being temporarily blocked by Amazon, or the Telegram API returning Rate Limit 429) does not affect the rest of the ecosystem. The messages remain secure in the queues and are reprocessed when the system stabilizes.

## 2. Communication Pattern and Queues (Message Broker)
The system uses **RabbitMQ** (via CloudAMQP) as its backbone. The messaging topology is designed to ensure asynchronous processing, failure retention, and complete observability.

* **Exchange Pattern:** A main Exchange will be used, such as `tracker.direct.exchange`, routing messages to specific queues through *Routing Keys*.

* **Queue Names (Main Queues):**
  * `item.validation.queue`: Receives raw URLs from the API (Telegram Gateway) for background processing (ASIN parser, image and title capture).
  * `scrape.jobs.queue`: Fed by the *Scheduler*, contains the commands (ASINs and IDs) that instruct the scrapers to perform price scans.
  * `price.decision.queue`: Receives events emitted by the scrapers informing that a price was updated in the database. The Decision Engine consumes this queue to cross-reference the new price with user rules.
  * `telegram.notification.queue`: Fed by the Decision Engine, contains ready messages (approved alerts after *cooldown* verification) for dispatch on Telegram.
  * `user.maintenance.queue`: Administrative queue triggered by critical failure events (e.g., bot blocked by the user) for executing the *Hard Delete* (cleanup of state and rules).

* **Strict Messaging Contracts (Pydantic):**
  * No worker can consume or publish generic Python dictionaries (`dict`). All payloads entering or leaving RabbitMQ must be validated by **Pydantic schemas** (e.g., `ScrapeCommandSchema`). Any message that fails schema validation at the destination will be immediately rejected (avoiding null key errors at runtime).

* **QoS and Fair Dispatch (Prefetch Count):**
  * All consumers (workers) MUST compulsorily configure the QoS limit on the `aio-pika` connection (e.g., `prefetch_count=10`). This prevents RabbitMQ from unloading thousands of messages at once onto a single newly started worker, ensuring fair load balancing (Fair Dispatch) among all active instances of the same service.

* **Dead-Letter Queues (DLQs) and Retries:**
  * Resilience (one of the pillars of the PRD) will be ensured through 1-to-1 mapping of DLQs. Each main queue will have its respective dead-letter queue (e.g., `telegram.notification.dlq`, `scrape.jobs.dlq`).
  * **Retry Policy:** Messages that fail (e.g., Amazon 503, Telegram 429, Database Timeout) will receive a *NACK* and undergo *Exponential Backoff* (progressive delay). After the maximum number of retries (e.g., 3 times), the message is sent to the corresponding DLQ so as not to block the flow and to allow monitoring (via Grafana) and manual/future reprocessing.

* **Base Header Structure (Payload/Metadata):**
  * To support the observability (Distributed Tracing) required in the PRD and facilitate testing (TDD), **all** messages injected into RabbitMQ must necessarily share a standard metadata structure (Wrapper or native AMQP Headers):
    * `trace_id` (UUID): Generated at the moment the action begins (e.g., webhook entry or cron trigger). Accompanies the data through all workers for tracking in *Sentry/Structured Logging*.
    * `timestamp` (ISO 8601): Exact date and time the event was generated. Also used to validate the TTL (Time-To-Live) of the message and avoid sending *Stale Data* (delayed alerts).
    * `retry_count` (Integer): Retry counter to manage the DLQ routing policy.

## 3. Agent Catalog (Workers)

### 3.1. API / Telegram Gateway Agent
* **Implementation Status:** [x] **Skeleton Created** | [ ] TDD/Tests | [ ] In dev | [ ] Completed
* **Primary Responsibility:** Synchronous entry point of the system. Receives Telegram webhooks (messages, commands, links), validates the user, enforces quota rules (limit of 50 ASINs), and queues heavy processing to avoid slow response times to the user.
* **Specific Tech Stack:** `FastAPI`, `aiogram` (or native `httpx` requests for webhook), `aio-pika`, `SQLAlchemy (asyncpg)`.
* **Triggers (Input Triggers):** External HTTP POST request triggered by the Telegram API.
* **Actions and Business Logic (Core Logic):** 
  1. Authenticates and extracts the `chat_id` and the message.
  2. Identifies if it is a CRUD command (`/list`, `/pause`) or a URL submission.
  3. If URL, counts the user's records in the database. If >= 50, returns a block and instructs the use of `/request_upgrade`.
  4. If < 50, publishes an `ItemValidationCommand` on the broker, responds to Telegram with a "Processing link...", and closes the request.
* **Outputs (Published Events / Outputs):** 
  * `ItemValidationCommand` injected into `item.validation.queue`.
  * HTTP 200 OK response to Telegram.
* **Data Access (State & Storage):** PostgreSQL (Read on `Users` for quota validation, and basic CRUD operations on `User_Products` tables).
* **Error Handling and Resilience:** 
  * Must respond HTTP 200 to Telegram even in the event of an internal failure, so that Telegram does not infinitely resend the same webhook (causing a request loop).
* **Test Scenarios (TDD):**
  * *Happy Paths:* User sends a valid link and has 10 registered items -> receives 200 OK, message injected into the queue.
  * *Edge Cases:* User sends a link having exactly 50 items -> rejected by quota, queue is not triggered. User sends random text ("hello") -> responds with a help message.
  * *Sad Paths / Resilience:* RabbitMQ is down -> gateway catches the network exception, warns the user "System currently unavailable" (HTTP 200 for Telegram).

### 3.2. Warm-up / Validation Worker
* **Implementation Status:** [x] **Skeleton Created** | [ ] TDD/Tests | [ ] In dev | [ ] Completed
* **Primary Responsibility:** Take raw links just sent by users, clean useless parameters, discover the true ASIN (resolving short links like `amzn.to`), extract the official photo and title from Amazon, and consolidate the registration.
* **Specific Tech Stack:** `aio-pika`, `httpx` (for requests and redirects), `beautifulsoup4`, `SQLAlchemy`.
* **Triggers (Input Triggers):** Consumption of the `item.validation.queue` queue.
* **Actions and Business Logic (Core Logic):**
  1. Follows any HTTP redirects (e.g., `amzn.to/xyz` -> `amazon.com.br/dp/B08...`).
  2. Uses Regex to extract the clean ASIN.
  3. Checks if the ASIN already exists in the `Products` database. If not, makes a lightweight request to Amazon to get `<title>` and image.
  4. Saves/Updates `Products`, creates the relationship in `User_Products`.
* **Outputs (Published Events / Outputs):** 
  * `AlertTriggeredEvent` (of type 'system_message') injected into `telegram.notification.queue` containing the confirmation ("Product registered!"). **Note:** This worker NEVER calls the Telegram API directly.
* **Data Access (State & Storage):** PostgreSQL (Insert/Update in `Products` and `User_Products`).
* **Error Handling and Resilience:**
  * Broken link / 404 Page -> Sends an event to the notification queue informing the user of the error, and drops the current message (ACK).
  * Amazon Captcha Block -> NACK and throws it back into the queue (retry).
* **Test Scenarios (TDD):**
  * *Happy Paths:* Dirty affiliate URL -> parser extracts the ASIN correctly, inserts into the database, notifies user.
  * *Edge Cases:* Two users send the same ASIN in the same second -> Handle *Race Condition* in the database (UPSERT / ON CONFLICT DO NOTHING).
  * *Sad Paths / Resilience:* Amazon blocking warm-up requests (503) -> worker requeues the message; after 3 attempts, goes to the DLQ and the user receives "Temporary error registering product".

### 3.3. Cron / Scheduler Agent
* **Implementation Status:** [x] **Skeleton Created** | [ ] TDD/Tests | [ ] In dev | [ ] Completed
* **Primary Responsibility:** Passive orchestrator. Wakes up at defined intervals, scans the database for products that need to be updated, and packages jobs in the Scraper queue.
* **Specific Tech Stack:** Python script (`asyncio`) packaged in a native host Cron Job, or a library like `APScheduler`. `SQLAlchemy`, `aio-pika`.
* **Triggers (Input Triggers):** Static time cron (e.g., every 6 hours).
* **Actions and Business Logic (Core Logic):**
  1. Query the DB searching for items where `status = 'ACTIVE'`.
  2. Optional: Filters by `last_checked_at < NOW() - 4 hours` to avoid unnecessary repetitions.
  3. Iterates (in chunks of 50) converting the results into `ScrapeCommand` payloads with priority level.
* **Outputs (Published Events / Outputs):** Hundreds/Thousands of `ScrapeCommand` in the `scrape.jobs.queue` queue.
* **Data Access (State & Storage):** PostgreSQL (Exclusive reading on the `Products` table).
* **Error Handling and Resilience:** If it fails in the middle of the batch, it must be idempotent (running it again will not duplicate records in the scraper).
* **Test Scenarios (TDD):**
  * *Happy Paths:* 500 active products in the database -> Scheduler generates and publishes exactly 500 messages in RabbitMQ and terminates.
  * *Edge Cases:* Zero products registered or all with `IDLE`/`PAUSED` status -> Executes successfully, but publishes zero messages.
  * *Sad Paths / Resilience:* Loss of connection with the Message Broker in the middle of the iteration -> must log the error, not crash, and ensure that in the next Cron round the pending batch is sent.

### 3.4. Scraper Worker
* **Implementation Status:** [x] **Skeleton Created** | [ ] TDD/Tests | [ ] In dev | [ ] Completed
* **Primary Responsibility:** The "factory floor worker". Focuses purely on downloading the Amazon HTML passing through the protections, performing DOM parsing, and checking if there are new prices. Scales horizontally (there can be 5, 10 simultaneous instances).
* **Specific Tech Stack:** `aio-pika`, `httpx` (with manual Header manipulation), `beautifulsoup4`, `SQLAlchemy`.
* **Triggers (Input Triggers):** Consumption of the `scrape.jobs.queue` queue.
* **Actions and Business Logic (Core Logic):**
  1. Rotation (Spoofing) of the `User-Agent` Header. Adds `Jitter` (1-3s sleep).
  2. Downloads the ASIN page. Searches for the Buy Box (`price_full`) and the "cash payment" description (`price_discount`).
  3. Checks "Out of stock" status.
  4. Queries the last price of this ASIN in the DB. If it is the same as the new one, only updates the `last_checked_at` of the Product (to save space).
  5. If it is different, saves a new historical record in `Price_History` and publishes an alert.
* **Outputs (Published Events / Outputs):** 
  * `PriceUpdatedEvent` published in `price.decision.queue` **only** if the price has changed.
* **Data Access (State & Storage):** PostgreSQL (Read/Write in the `Price_History` table and update in `Products`).
* **Error Handling and Resilience:** 
  * 503 Error / Dog Page (Captcha) -> Throws it back into the queue (NACK) with delay (Backoff).
  * 404 Error returned by > 3 collections -> Changes product status to `UNAVAILABLE` and stops trying.
* **Test Scenarios (TDD):**
  * *Happy Paths:* Receives valid ASIN, downloads mocked HTML with reduced price -> Saves `Price_History`, emits `PriceUpdatedEvent`.
  * *Edge Cases:* Product out of stock (no buy button) -> Identifies as NULL / Out of stock, does not emit event with value "R$ 0.00". Price identical to the previous scan -> Ignores insert in the database and does not trigger decision queue.
  * *Sad Paths / Resilience:* Amazon changes the CSS class of the price -> Parser fails gracefully (throws trackable ParsingError exception in Sentry), does not save corrupted data.

### 3.5. Decision Engine Worker
* **Implementation Status:** [x] **Skeleton Created** | [ ] TDD/Tests | [ ] In dev | [ ] Completed
* **Primary Responsibility:** Analyze price changes in real time and decide *who* should be notified, applying anti-spam restrictions (Cooldown).
* **Specific Tech Stack:** `aio-pika`, `SQLAlchemy`, `redis.asyncio`.
* **Triggers (Input Triggers):** Consumption of the `price.decision.queue` queue.
* **Actions and Business Logic (Core Logic):**
  1. Receives a variation event (E.g.: B08... dropped from R$300 to R$200).
  2. Fetches all `user_id` and `target_price` associated with this ASIN.
  3. For each user, if R$200 <= `target_price`, checks Redis for the key `lock:alert:{user_id}:{asin}`.
  4. If the key does not exist, generates the `AlertTriggeredEvent`, registers the key in Redis (with a 12h TTL), and updates `last_notified_at` in the DB.
* **Outputs (Published Events / Outputs):** Multiple `AlertTriggeredEvent` published in `telegram.notification.queue`.
* **Data Access (State & Storage):** PostgreSQL (Reading rules from `User_Products`). Redis (Write/Read of TTL cooldown keys).
* **Error Handling and Resilience:** 
  * If Redis is down, performs Fallback: checks the `last_notified_at` field in PostgreSQL and uses it as the base cooldown calculation in memory.
* **Test Scenarios (TDD):**
  * *Happy Paths:* 5 users follow an item, the price hits the target for 3 of them -> 3 messages dispatched.
  * *Edge Cases:* The price hits a user's target, but a key exists in Redis -> Trigger silently aborted (cooldown respected).
  * *Sad Paths / Resilience:* Redis returns ConnectionRefused -> Worker does not die, applies fallback using the relational table.

### 3.6. Notification Worker
* **Implementation Status:** [x] **Skeleton Created** | [ ] TDD/Tests | [ ] In dev | [ ] Completed
* **Primary Responsibility:** Receive alert orders and interact with Telegram via HTTP to deliver the final messages with actionable links. Also responsible for the forced termination of the lifecycle (Hard Delete) in the event of a ban.
* **Specific Tech Stack:** `aio-pika`, `aiogram` (or `httpx`), `SQLAlchemy`.
* **Triggers (Input Triggers):** Consumption of the `telegram.notification.queue` and `user.maintenance.queue` queues.
* **Actions and Business Logic (Core Logic):**
  1. (Notification): Takes the data, composes a template in Markdown/HTML (truncating large titles), inserts affiliate tag if applicable, and does a POST to the Telegram Bot API.
  2. (Maintenance): If it receives a block event, removes the `User` and cascades cleaning `User_Products`. Scans `Products` to mark as `IDLE` if no other user is following.
* **Outputs (Published Events / Outputs):** External request (HTTP). `UserBlockedEvent` event in the maintenance queue.
* **Data Access (State & Storage):** Main DB (Restricted access only for cascading removal (Hard Delete)).
* **Error Handling and Resilience:** 
  * Telegram `429 Too Many Requests` -> Repositions in the queue, respecting the `Retry-After` HTTP header.
  * Telegram `403 Forbidden (bot blocked by user)` -> Cancels resends and emits `UserBlockedEvent` on the Broker.
* **Test Scenarios (TDD):**
  * *Happy Paths:* Telegram API returns 200 OK -> ACK on the message ending the cycle.
  * *Edge Cases:* Product title with special characters (`*`, `_`, `[`) breaking Telegram's MarkdownV2 -> Escape regex (sanitization) ensures sending without failing the request with a 400 Error.
  * *Sad Paths / Resilience:* Telegram API returns `429 Too Many Requests` -> The worker reads the `Retry-After` HTTP header, rejects the message (NACK) and it is forwarded with dynamic delay. Returns `403 Forbidden` -> Injects command into `user.maintenance.queue` and discards alert.

## 4. Global Policies and System Constraints (Global Constraints)
<!-- Transversal rules that all agents must respect to ensure resilience and zero cost. -->

* **Repository Architecture (Monorepo):**
  * The application must be built in a single repository to centralize dependencies. There will be a unified codebase (shared folders like `models/`, `schemas/`, `core/`).
  * There will be only one main `Dockerfile`. The execution of each agent in the cloud infrastructure will take place by passing the respective *entrypoint* per command at startup (e.g., `python -m workers.scraper` or `uvicorn api.main:app`).

* **Database Versioning (Alembic):**
  * It is **prohibited** to create or alter tables manually in the database (e.g., via the Supabase panel). Any and all data modeling must reflect the SQLAlchemy Models and be compulsorily managed and versioned using **Alembic**, ensuring a history of migrations (`migrations/`).

* **Graceful Shutdown:**
  * All workers must intercept system signals (`SIGINT`, `SIGTERM`). When they receive the shutdown order (e.g., Cloud Run scaling to zero), the worker must stop consuming new messages, finish the ongoing processing, return (NACK) the unprocessed messages, and safely close the connections with PostgreSQL and RabbitMQ to avoid "leaking" and state corruption.

* **Idempotency (At-Least-Once Guarantee):**
  * Due to the nature of RabbitMQ (which can deliver the same message twice in the event of a network failure), **all consumers must be idempotent**. Processing the same notification or price update event twice must result in the same final state, without duplication or failure.

* **Strict Timeouts and Circuit Breakers (Bottleneck Prevention):**
  * All external network calls (Amazon, Telegram API) using `httpx` or `aiohttp` MUST have an explicit timeout configured (e.g., `timeout=10.0` seconds). **Prohibited** to use requests without timeout, which can cause the perpetual freezing of the worker.
  * If a scraper fails consecutively due to *Timeout* or 503 Error (e.g., 5 failures in a row), the worker must implement a "Circuit Breaker", pausing its own consumption of the queue for 2 minutes so as not to burn attempts in vain and worsen the IP block.

* **DLQ Lifecycle:**
  * Messages that fall into the DLQs must have an `x-message-ttl` configured (e.g., 7 days). After this period, if they are not manually reprocessed, they are automatically discarded to protect the broker's Free Tier disk quota.

* **Concurrency and Scaling (Connection Limits):** 
  * **In the Database:** Since we are using databases in *Free Tier* (e.g., Supabase/Oracle), the maximum number of simultaneous connections is strictly limited. **No worker should connect directly to the main PostgreSQL.** All connections must compulsorily pass through `PgBouncer` (Connection Pooler). Asynchronous workers (e.g., Scraper) must use semaphores (`asyncio.Semaphore`) to limit simultaneous requests and not exhaust the PgBouncer pool.
  * **Horizontal Scaling:** The initial limit will be a maximum of 3 simultaneous instances of the `Scraper Worker` running on free providers (e.g., Google Cloud Run/Render).

* **Observability (Structured Logs and Privacy):** 
  * **Format:** The use of the native `logging` library in text format is **prohibited**. All workers must emit logs in JSON format (using libraries like `structlog`), allowing clean ingestion in Grafana/ELK.
  * **Tracing:** Every transacted message must carry the `TraceID` in the header. The log must contain minimally: `{"timestamp": "...", "level": "...", "worker": "Scraper", "trace_id": "...", "asin": "B08...", "message": "..."}`.
  * **PII Protection (Privacy Law):** It is strictly **prohibited** to log the Telegram username, phone number, or raw URL that contains personal identifiers. Always use the `user_id` (internal UUID) in log messages.

* **Hard Stop (Free Tier Cost Protection):** 
  * The project has zero tolerance for unexpected costs.
  * **Messaging Quota (CloudAMQP):** The limit of the free plan is 1,000,000 messages/month. A monitoring service (or the Scheduler itself) must check the consumption via the RabbitMQ API. If consumption reaches **95% of the monthly quota**, the `Cron / Scheduler Agent` must automatically enter interrupt mode (Hard Stop), pausing new scans and logging a critical alert.
  * The application must be coded with the philosophy of **"Accepting unavailability for the sake of zero cost"**. If the limits of AWS, Supabase, or CloudAMQP are reached, the application must fail safely, without generating financial charges (Billing Overruns).

## 5. Testing Guidelines (TDD & Quality)
<!-- Strict rules for PR approval and test-driven development. -->

* **Mandatory Red-Green-Refactor:** No business code will be written before its corresponding test. The test suite must drive the architecture modeling.
* **Local Environment (DevEnv - Docker Compose):** Before starting development, a local `docker-compose.yml` file must be created providing PostgreSQL, Redis, and RabbitMQ containers. Developers must not point the local environment to production/staging databases hosted in the cloud.
* **Minimum Failure Coverage:** All workers must start by writing exception tests (*Sad Paths*). Before testing if the price is saved correctly, one must test the worker's behavior when the database refuses the connection, when the network times out, or when the RabbitMQ payload comes malformed. The minimum required code coverage (`pytest-cov`) is 85%.
* **Mandatory Mocks (Network Isolation):** 
  * It is **prohibited** to hit real external APIs (Amazon, Telegram API) during the execution of automated unit or continuous integration (CI) tests.
  * HTTP responses (200 OK, 429 Rate Limit, 503 Captcha) must be emulated using libraries like `respx` or `responses`.
* **Testcontainers for Integration:** Tests must not use unrealistic in-memory databases like SQLite if production runs on PostgreSQL. For integration tests, real ephemeral containers of PostgreSQL, Redis, and RabbitMQ must be orchestrated (using `testcontainers-python`), ensuring that the SQL syntax and messaging features (such as DLQs) are tested on the same production engine.
* **State Isolation:** A test can never depend on the result of another previous test. The ephemeral databases and keys in Redis must be explicitly truncated/cleared in the *teardown* step (`yield` in the `pytest` fixture) with each test execution.

## 6. Environment Variables Dictionary (Environment Secrets)
<!-- Necessary configurations for the agents. Never expose these values in the source code (.env must be ignored in git). -->

| Variable | Use / Component / Agent | Criticality | Description and Rules |
| :--- | :--- | :--- | :--- |
| `RABBITMQ_URI` | **All Workers** and **API Gateway** | **Critical** | AMQP connection string with credentials (e.g., CloudAMQP URL). Essential for the entire system event bus. |
| `TG_BOT_TOKEN` | **API Gateway** and **Notification Worker** | **Critical** | Token generated by Telegram's BotFather. Necessary to validate webhooks on entry and dispatch messages on exit. |
| `DATABASE_URL` | **Gateway**, **Validation**, **Scheduler**, **Scraper**, **Decision**, **Notification** | **Critical** | PostgreSQL connection string. **Mandatory** to point to the `PgBouncer` (pooler) port and not directly to the database, to avoid connection exhaustion in the cloud. |
| `REDIS_URL` | **Decision Engine Worker** | **High** | Redis connection string (e.g., Upstash/RedisLabs). Used to manage TTL keys (Anti-spam *Cooldown*) and fast caching of the lowest historical price. |
| `ADMIN_TELEGRAM_ID` | **API Gateway** and **Logging System** | **Medium** | Administrator's `chat_id` (Dev/SRE). Used to route quota `/request_upgrade` requests and to receive critical infrastructure alerts (e.g., frozen queue). |
| `MAX_USER_QUOTA` | **API Gateway** | **Low** | Defines the global limit of products per default user (Default: `50`). Allows dynamic adjustment without needing deployment. |
| `SCRAPE_INTERVAL_HOURS`| **Cron / Scheduler Agent** | **Medium** | Defines the base interval between batch scans (Default: `6`). Essential for controlling the volume of requests and protecting the RabbitMQ free quota. |
| `APP_ENV` | **All Workers** | **Medium** | Defines the current environment (`development`, `testing`, `production`). Alters framework behaviors, ignoring strict validations only in dev. |
| `LOG_LEVEL` | **All Workers** | **Low** | Verbosity level of *Structured Logging* (`DEBUG`, `INFO`, `WARNING`, `ERROR`). In production, it must be kept at `INFO` to save storage space on free providers. |