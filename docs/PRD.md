# PRD Structure: Amazon_Price_Tracker_Alert_Engine

## 1. Document Metadata
* **Product/Project Name:** Amazon Price Tracker & Alert Engine
* **Document Version:** 05
* **Update Date:** September 6, 2026
* **Author(s):** Gabriel
* **Status:** Phase 1 Closed

### 1.1. Changelog / Architectural Decision Records (ADR)
* **[09/06/2026] - v05:** Formally closed Phase 1. All HIGH-priority tech debts resolved, system functional and ready for production deployment. Remaining accepted tech debts deferred to Phase 2.
* **[09/06/2026] - v04:** Resolved TD-07 and TD-09. Implemented CloudAMQP quota monitoring with Scheduler integration and added 36 async unit tests for workers. Overall test coverage reached 64%.
* **[09/06/2026] - v03:** Documentation alignment. Added TD-09 (Worker Unit Test Coverage) to Phase 1 Known Tech Debts section. Coverage target adjusted to 60% for Phase 1 realism.
* **[09/06/2026] - v02:** Phase 1 implementation complete. All 6 workers implemented and operational. Added known tech debts from Phase 1 review.
* **[09/05/2026] - v01:** Initial draft version.

---

## 2. Overview (Executive Summary)

**The problem:** Consumers and frequent shoppers constantly miss lightning deals, market fluctuations, and significant price drops on Amazon due to the unfeasibility of manually monitoring desired products. Generic tracking solutions often suffer from notification latency (delivering the alert when the promotional stock has already run out), lack of flexibility in trigger rules, or excessive spam (repetitive alerts about the same variation).

**The solution:** The Amazon Price Tracker & Alert Engine is an event-driven backend application designed to automate the scanning and price monitoring of Amazon products (inserted via ASIN/Link or public wishlists). Using a resilient scraper with anti-bot evasion and an asynchronous messaging architecture, the system records the price history and runs a decision engine (Decision Engine) to trigger direct, real-time notifications (initially via Telegram) as soon as specific discount criteria are met.

**Target audience:**
* Smart Shoppers and deal hunters looking to optimize their purchasing power.
* Technology enthusiasts and frequent consumers of the Amazon ecosystem.
* (Future potential) Small resellers or retail arbitrage professionals who rely on speed and historical data for financial decision-making.

**Value Proposition:** Unlike manual checks or slow synchronous systems, the event-driven architecture ensures that the detection of a price drop generates an actionable notification almost in real time. The technical differentiator lies in the robustness of the collection (capturing variations of full price vs. Pix/cash), the intelligence of the alerts (based on granular rules such as all-time low or percentage drop), and the respect for the user's attention (through strict cooldown policies that prevent notification fatigue).

---

## 3. Objectives and Metrics (Goals & Success Metrics)

### Business/Product Objectives:
* Validate the tracking model with a functional MVP, focused on monitoring individual items and delivering precise alerts via Telegram.
* Build a reliable historical database of Amazon prices to enable advanced analytics (such as "all-time low" and "downward trend").
* Ensure user trust by delivering highly actionable notifications, eliminating noise (false positives), and preventing spam.

### Success Metrics (KPIs):
* **Collection Success Rate (Scraping Success Rate):** > 95% of scheduled scans successfully completed, without anti-bot blocks or parsing (data extraction) failures.
* **Alert Latency:** Time of less than 5 seconds between the detection of a price drop in the database and the delivery of the message to the user's Telegram.
* **False Positive Rate:** < 1% of alerts triggered incorrectly (e.g., scraper reading error when capturing the price of a third-party product or shipping).
* **Cooldown Efficiency:** 100% compliance with rules for suppressing repeated alerts for the same product/user within the configured interval.

### Technical Objectives:
* **Scalability:** The system must be able to support the simultaneous monitoring of at least 10,000 items (ASINs) in the MVP phase, without bottlenecks in queue processing.
* **Resilience:** Full implementation of Dead-Letter Queues (DLQs) and retry policies with exponential backoff to handle temporary unavailabilities of the Telegram API or the database.
* **Availability (Uptime):** 99.9% uptime for the decision engine and the item management API.
* **Resource Optimization:** Maintain a low computational cost through the efficient use of instances, connection pooling, and controlled concurrency in the collection workers.

---

## 4. Scope and Phases (Scope & Phasing)

### Phase 1 (MVP): Essential features for the initial launch
* **Item and Quota Management:** Registration, listing, pausing, and removal of individual products. The system will accept raw/dirty links (like those generated by the app's "share" button), and the backend will perform automatic cleaning (parser) to extract the ASIN and the canonical link. There will be a strict limit of 50 simultaneously tracked products per user (expandable to 100 upon specific authorization).
* **Collection (Scraping) and Domain Scope:** Daily/periodic extraction of basic metadata (title, image) and prices (full and cash/Pix). Identification of "Out of stock" status. The scope will be strictly restricted to Amazon Brazil (amazon.com.br). The collection will always capture the standard price (simulating an anonymous/logged-out user), ignoring exclusive values for Prime subscribers.
* **Scheduling (Scheduler):** Execution of batch scans at fixed intervals (e.g., every 4 or 6 hours) for all active ASINs in the database. In this phase, there will be no frequency customization per user.
* **Storage and History:** Structured recording of prices in a time series for the calculation of the all-time low and average price.
* **Decision Engine and Cooldown:** Support for two initial triggers: "Below target price X" and "Reached the all-time low". Implementation of a global cooldown policy (e.g., do not alert the same item to the same user in the next 12 hours).
* **Messaging and Notifications:** Queue/topic-based architecture (event-driven) with exclusive integration to Telegram (via Bot API) for sending the alert and direct link. Implementation of DLQ (Dead-Letter Queue) for delivery retries.
* **User Lifecycle (Hard Delete):** If the Telegram API returns an error stating that the user blocked the bot, the system will perform a hard delete of all user data and their respective tracking rules from the database, with no possibility of recovery.

### Phase 2: Planned features for the next iteration
* **Batch Import:** Support for automatic reading and tracking of Public Amazon Wishlists.
* **Advanced Alert Rules:** Triggers based on a minimum percentage drop (e.g., "Notify me if it drops 15% compared to the 30-day average").
* **New Delivery Channels:** Integration with Discord, WhatsApp, or E-mail.
* **Advanced Anti-bot Evasion:** Integration with commercial proxy rotation services and Captcha solvers, in case Amazon blocks increase.
* **Graphical Interface (Frontend):** Creation of a simple web dashboard for visual item management and visualization of price history charts, reducing reliance on Telegram chat commands.

### Out of Scope: What will not be built at this time
* **Auto-Checkout:** The system will not make automated purchases (buying bot); it will only send the link for the user to complete the transaction manually.
* **Multiple Retailers and Regions:** Price tracking on other platforms (Mercado Livre, Kabum, Magalu) or in other Amazon regions (e.g., .com or .co.uk).
* **Price Prediction (Machine Learning):** The system will report past and present history, but will not use AI to predict future price drop trends.
* **Shipping Cost Tracking:** The tracking will focus on the product's value, ignoring shipping variations by zip code.

---

## 5. Personas and Use Cases (User Stories)

### Personas

**Persona 1: The Deal Hunter (Smart Shopper - End User)**
* **Profile:** Frequent digital consumer, pragmatic and with a defined budget. Knows what they want to buy (electronics, books, consumer goods), but has no immediate urgency and prefers to wait for the best financial moment.
* **Needs:** Speed in notification (knows that promotional stocks run out fast), ease of registering products without leaving the phone, and zero tolerance for spam or false alerts.
* **Interaction with the System:** Interacts exclusively via Telegram, sending links and receiving alerts.

**Persona 2: The System Administrator (Dev/SRE - Operator)**
* **Profile:** Backend infrastructure maintainer. Focused on stability, costs, and observability.
* **Needs:** Ensure that collection workers are not blocked by Amazon, monitor the size of message queues, and manage delivery failures.
* **Interaction with the System:** Accesses logs, metrics dashboards, database, and monitors messaging queues (e.g., RabbitMQ/SQS) and Dead-Letter Queues (DLQs).

### Main User Journey (Happy Path)
1. **Discovery and Registration:** The user finds a product of interest on Amazon (e.g., an SSD), copies the link, and sends it to the Price Tracker Telegram Bot.
2. **Trigger Configuration:** The Bot responds by recognizing the product (returns the title and current price extracted in real time or via the database) and requests the goal configuration: "What is your target price?" or "Notify when it hits the all-time low?". The user sets the rule.
3. **Asynchronous Processing (Background):** The system registers the item in the database, and the Scheduler adds the ASIN to the periodic scan queue.
4. **Data Collection:** In one of its cycles (e.g., every 6 hours), the Scraper accesses the product page, bypasses basic protections, collects the new price, and updates the history in the database.
5. **Decision Engine:** A "Price Update" message is published to the Message Broker. The Decision Worker consumes this message and verifies that the new price ($299) is lower than the user's target ($300).
6. **Cooldown Validation:** The system checks if this user has already received an alert for this product in the last 12 hours. Since they haven't, it approves the trigger.
7. **Notification and Conversion:** The Telegram Bot receives the command and instantly sends the message: "Price Alert! The SSD dropped to $299. [Buy here]". The user clicks the link and completes the purchase on Amazon.

### User Stories

**Input and Management Module (CRUD)**
* **US01:** As a user, I want to send an Amazon link to the bot so that the system automatically registers the product in my tracking list, extracting the ASIN without me having to type it.
* **US02:** As a user, I want to query the list of my active items to know which products are currently being monitored.
* **US03:** As a user, I want to be able to pause or delete the tracking of a specific product to stop receiving alerts after having already made the purchase or lost interest.
* **US04:** As a user, I want to set an exact target price (e.g., R$ 150.00) during item registration so that the alert is triggered only when this financial condition is met.
* **US05:** As a user, I want to be able to edit the target price of a product already registered in my list, so that I can adjust my goal without needing to delete and resend the link.
* **US06:** As a system, I want to limit the registration to 50 products per user and block the insertion of the 51st item, sending a warning message instructing the user to type the command `/request_upgrade` (which will trigger an alert to the administrator's dashboard to manually approve the quota expansion in the database).

**Collection and Analysis Module (Scraping)**
* **US07:** As a system (Scraper), I want to differentiate the "Full Price" from the "Pix/Cash Price" during the scan to ensure that the comparison in the decision engine is based on the actual most advantageous value.
* **US08:** As a system (Scraper), I want to identify when a product has an "Out of stock" status or returns a 404 error to avoid saving false values (like zero) and corrupting the all-time low metric.
* **US09:** As an administrator, I want the collector to make random intervals (jitter) between requests to avoid triggering Amazon's anti-bot mechanisms.

**Rules and Notification Module (Events)**
* **US10:** As a user, I want to receive the price drop notification on my Telegram in real time, containing the product name, current price, achieved variation, and direct link, so that I can buy before the stock runs out.
* **US11:** As a system (Decision Engine), I want to apply a 12-hour cooldown policy after triggering an alert for a product to a user, to avoid flooding their chat if the price fluctuates by cents throughout the day.
* **US12:** As a system (Notifier), I want to perform a hard delete of all active data and rules of a user immediately after receiving an error from the Telegram API indicating that the user blocked the bot, ensuring database cleanup and processing savings.
* **US13:** As an administrator, I want alerts that fail to be sent to Telegram to be directed to a Dead-Letter Queue (DLQ) so that the system attempts to resend (retry) after a few minutes, ensuring delivery resilience.

---

## 6. Functional Requirements

### 6.1. Input and Management Module (Item CRUD)
* **ASIN Extraction and Sanitization:** The system must receive full or shortened URLs (amzn.to) via Telegram. A parser service must resolve redirects, clean tracking parameters (e.g., `?tag=...`, `&ref=...`), and extract the ASIN (Amazon Standard Identification Number) code accurately (usually via Regex).
* **Metadata Validation (Asynchronous):** Upon receiving a new ASIN, the system must not make the user wait. The bot must respond instantly confirming receipt of the link and queue the registration. A background worker will do the "warm-up", validating the product's existence and capturing the official Amazon title and the main image. Then, it notifies the user of the success and asks for the rule definition (target price).
* **Quota Control:** Before accepting and processing the registration of a new item, the system must count the products already registered by the user. If the limit of 50 products is reached, the insertion must be blocked, and the bot will return a message informing the exceeded limit and instructing the use of the `/request_upgrade` command to notify the administrator and request the expansion authorization.
* **State Control and Garbage Collection:** Products in the database must have a state machine:
  * **ACTIVE:** Actively being tracked.
  * **PAUSED:** Paused by the user (does not generate alerts and ignores scans if no other user is following the same ASIN).
  * **UNAVAILABLE:** Product removed from the Amazon catalog (404 Error returned multiple times).
  * **IDLE:** Status automatically assigned by the system when the last User_Product relationship of an ASIN is undone (deletion or hard delete of the user). This prevents the Scheduler from continuing to waste collection requests on products that no one follows anymore.
* **User-Item Association (Many-to-Many):** Multiple users can track the same ASIN with different alert rules. The system must store only one product record and relate it to the different Telegram IDs and their respective rules.

### 6.2. Collection Module (Scraper & Scheduler)
* **Scheduling Policies (Scheduler):**
  * An orchestrator process must queue extraction jobs (messages) in a Message Broker every X hours (configurable base frequency, e.g., every 6 hours).
  * Optimization: More popular items (with more users following them) or with a history of high volatility can have their frequency increased automatically.
* **Extraction and DOM Parsing Rules:**
  * The Scraper must search for the CSS/XPath selectors corresponding to the Buy Box Price (main price) and investigate the presence of discounts for cash/Pix payments (usually described in the text below the full price).
  * Depletion: The system must explicitly detect strings like "Currently unavailable" or the absence of the "Add to cart" button, recording the price status as NULL or signaling an out-of-stock flag, so as not to record "R$ 0.00".
* **Anti-Bot Mechanisms and Error Handling:**
  * Rotation and Spoofing: Rotation of User-Agents (simulating different browsers and devices) and HTTP Headers.
  * Jittering: Insertion of random delays (e.g., 2 to 7 seconds) between requests sent by the same worker.
  * Captcha/503 Handling: If Amazon returns a temporary block (Dog Page / Captcha), the worker must not fail the item permanently; it must throw the message back to the queue with a retry delay.

### 6.3. History and Analysis Module
* **Time-Series Storage:** Every collected price that is different from the last collection must generate a new immutable record in the history, containing: `asin`, `price_full`, `price_discount`, `timestamp`. (Consecutive identical prices do not need new records, optimizing the database).
* **Asynchronous Metrics Calculation:**
  * Right after the persistence of a new price, the system recalculates the aggregations in the background: All-Time Low (ATL) and Average Price (last 30/90 days).
  * These aggregated data must be cached (e.g., Redis) for quick reading by the Decision Engine.
* **Anomaly Sanitization:** The system must ignore absurd variations (e.g., a drop from R$ 5,000 to R$ 10) which usually indicate scraper reading errors or scammer sellers in the marketplace.

### 6.4. Alert Rules Module (Decision Engine)
* **Triggers:** When the `price.updated` event is triggered, the Engine cross-references the new value with the rules in the users table. It must support:
  * Absolute Target Price: `New Price <= Price defined by the user`.
  * Percentage Drop (Phase 2): `New Price <= (30-day Average - X%)`.
  * Historical Record: `New Price < Recorded All-Time Low`.
* **Cooldown Policies (Anti-Spam):**
  * To avoid notifications for every penny fluctuation that Amazon makes via algorithm, the system must register a lock key (with Time-To-Live - TTL, e.g., 12 hours) after sending an alert for an ASIN to a User.
  * During this period, the Decision Engine ignores new low-price events for this combination (User_ID + ASIN).

### 6.5. Messaging and Notification Module
* **Event Structure (Pub/Sub):** Total decoupling. The Scraper only publishes `price.updated`. The Decision Engine consumes and publishes `alert.triggered`. The Notification Worker consumes `alert.triggered` and attempts to send it to Telegram.
* **Payload Formatting:** The alert sent to Telegram must be formatted in Markdown/HTML, containing:
  * Truncated title (for readability on mobile).
  * Previous Price vs. Current Price (highlighting the difference).
  * Clean URL with the embedded affiliate tag (optional, if you want to monetize).
* **Resilience (Retry, DLQ, and Deletion due to Block):**
  * Temporary Failures: If the Telegram API fails temporarily (e.g., 429 Too Many Requests error), the message receives a NACK (Negative Acknowledgement) and returns to the queue with Exponential Backoff (waits 5s, then 10s, then 30s). If it fails after the maximum limit, it goes to the Dead-Letter Queue (DLQ).
  * Hard Delete (Bot Block): If the Telegram API returns an error indicating that the user blocked the bot (e.g., Forbidden: bot was blocked by the user), the worker will not retry. Instead, it will trigger an asynchronous instruction to the database to immediately execute the definitive and unrecoverable deletion of all data for that user and their associated rules.

---

## 7. Non-Functional Requirements

### 7.1. Performance & Scalability
* **Parallel Processing:** The system must support the simultaneous execution of multiple scraping workers, scaling horizontally (adding new instances) according to the size of the scheduling queue, without causing deadlocks in the database.
* **Database Protection under Scale (Connection Pooling):** To support a sudden increase in workers without exhausting database connection limits, the architecture will use PgBouncer (combined with PostgreSQL) to manage and optimize the connection pool efficiently.
* **Messaging Throughput:** The Message Broker must be able to sustain peak publication/consumption of up to 1,000 messages per second (considering Black Friday or Prime Day scenarios, where thousands of prices drop simultaneously).
* **Acceptable Latency:** The total time between the detection of a price drop and the publication of the alert in the notification queue (Decision Engine processing) must not exceed 500 milliseconds (P95).

### 7.2. Reliability & Resilience
* **Availability (Uptime):** The core system (Item CRUD, decision engine, and Telegram Webhook routes) must have a 99.9% availability target.
* **External Component Fault Tolerance:** If AWS (Amazon) temporarily blocks scrapers or the Telegram API goes down, the core system must not fail. Network operations must have strict timeouts, circuit breakers, and backoff mechanisms.
* **State Isolation:** A collection worker crashing mid-request must not corrupt the item's state in the database. The corresponding message will not receive the ACK (acknowledgement) and will be reprocessed by another active worker.
* **Backup and Disaster Recovery Policy:** The PostgreSQL database must have automatic backup routines (e.g., daily snapshots) to ensure the integrity and rapid recovery of price history and user configurations in the event of a critical infrastructure failure.

### 7.3. Security & Privacy
* **Secrets Management:** Telegram API tokens, database credentials, and Broker connection strings must never be exposed in the source code. The system must strictly consume these variables via a secure environment (e.g., AWS Secrets Manager, HashiCorp Vault, or strict `.env` files).
* **Input Validation:** All data received from the user via Telegram (such as URLs or commands) must be strictly validated and sanitized to prevent injection attacks (SQL Injection, NoSQL Injection) or DoS (attempts to overload the queue by sending thousands of links in seconds).
* **PII (Personally Identifiable Information) Protection:** The system must avoid logging personally identifiable information. System logs should record "User ID 12345" instead of displaying real names or phone numbers associated with the Telegram account.
* **Legal Compliance and Data Retention (LGPD):** The system must operate in compliance with data protection laws. The hard delete routine (triggered by bot blocking) must ensure the permanent removal of user data from the active database. Additionally, log and backup retention policies must provide for the expiration and secure deletion of this information in defined cycles, avoiding lifetime storage.

### 7.4. Observability
* **Structured Logging:** All logs emitted by the services must follow a structured format (JSON), ensuring easy ingestion by analysis tools (e.g., ELK Stack, Datadog, or CloudWatch) and facilitating the search for failures in specific ASINs.
* **Application Metrics:** The application must expose an endpoint (e.g., via Prometheus) with real-time metrics, including:
  * Queue sizes (Pending, Processing, DLQ).
  * Scraper error rate per minute (blocks, 404, Captchas).
  * Number of alerts successfully processed and sent.
* **Distributed Tracing:** Every request that enters the system (e.g., a user command or a scheduled scan) must receive a unique TraceID. This ID must accompany the message through all queues and logs, allowing the tracking of the data's full lifecycle (from scraper to notification).
* **Infrastructure Alerts:** The system must have triggers to notify system operators (via a separate Telegram channel or Slack) if metrics degrade (e.g., DLQ exceeds 100 unprocessed messages or a critical database connection failure).

---

## 8. Architecture & Data Flow

### 8.1. Architecture Diagram (Logical View)
*(Placeholder for the visual diagram. Below is the description of the architectural blocks that will compose it)*

* **API / Telegram Gateway:** Synchronous entry point. Receives Telegram webhooks (user commands), manages requests, parses links, and interacts with the main database.
* **Cron / Scheduler:** Lightweight service responsible for injecting scan commands (jobs) into the scraping queue at predetermined intervals.
* **Message Broker (E.g., RabbitMQ, AWS SQS, or Kafka):** The core of the asynchronous architecture. Manages the Registration, Scraping, Decision, Notification, and Deletion queues, in addition to the Dead-Letter Queues (DLQs).
* **Scraper Workers:** Set of scalable consumers that take items from the queue, execute HTTP requests to Amazon, bypass blocks, and save new prices to the Database.
* **Decision Engine:** Service that consumes price update events, queries user rules and the cooldown cache, determining whether an alert should be generated.
* **Notification Workers:** Dedicated consumers to pick up validated alerts and dispatch them back to the Telegram API.
* **Data Layer:**
  * **Main Database (Relational):** PostgreSQL associated with PgBouncer (for connection pool management and scale protection). Stores structured entities (Users, Products, History).
  * **Cache/In-Memory (E.g., Redis):** Stores cooldown keys with TTL and quick-access metrics (e.g., updated All-Time Low).

### 8.2. Preliminary Data Model (Schema)

**Table: Users**
* `id` (UUID, Primary Key)
* `telegram_chat_id` (String, Unique) - Identifier on Telegram.
* `quota_limit` (Integer, Default: 50) - Limit of simultaneously allowed products (expandable via authorization).
* `created_at` (Timestamp)

**Table: Products**
* `id` (UUID, Primary Key)
* `asin` (String, Unique) - Product code on Amazon.
* `title` (String) - Extracted name.
* `url` (String) - Canonical link.
* `status` (Enum: ACTIVE, PAUSED, UNAVAILABLE, IDLE)
* `last_checked_at` (Timestamp) - Last successful scan.

**Table: User_Products (Subscriptions/Alerts - N:N Relationship)**
* `user_id` (UUID, Foreign Key)
* `product_id` (UUID, Foreign Key)
* `target_price` (Decimal/Float) - Target price set by the user (if applicable).
* `alert_on_all_time_low` (Boolean) - Trigger for all-time low.
* `last_notified_at` (Timestamp) - Date of the last alert (used to validate cooldown in the fallback).
* *Composite Primary Key of (user_id, product_id).*

**Table: Price_History**
* `id` (UUID, Primary Key)
* `product_id` (UUID, Foreign Key, Indexed)
* `price` (Decimal/Float) - Captured price.
* `is_discounted` (Boolean) - Whether the price refers to Pix/Cash.
* `created_at` (Timestamp) - Date and time of capture.

### 8.3. Messaging Contracts (Event Schema)

**Event 1: ItemValidationCommand (Warm-up/Registration Queue)**
Sent by the API right after the user sends the link, for background processing.
```json
{
  "event_id": "val-1122-ccdd",
  "telegram_chat_id": "987654321",
  "raw_url": "[https://amzn.to/](https://amzn.to/)...",
  "timestamp": "2026-09-05T09:50:00Z"
}

---

## 9. Phase 1 Known Tech Debts & Accepted Gaps

The following items were identified during Phase 1 implementation review and are intentionally deferred to Phase 2 or future iterations. They represent accepted trade-offs given the MVP scope and zero-cost constraints.

| # | Item | Location | Description | Impact |
|---|------|----------|-------------|--------|
| TD-01 | Product IDLE Transition | PRD 6.1, AGENTS 3.6 | When the last User_Product relationship is deleted, the product is hard-deleted rather than transitioning to IDLE status. The Scheduler will not waste resources on unfollowed products since they are removed entirely. | Low — Scheduler may occasionally attempt to scrape deleted products; requires future UPSERT logic |
| TD-02 | Race Condition (Concurrent ASIN Submission) | PRD 6.1, AGENTS 3.2 | Two users submitting the same ASIN simultaneously uses check-then-insert rather than database-level UPSERT/ON CONFLICT. Under high concurrency, a race condition could result in duplicate product records. | Medium — Rare in MVP scale; requires DB constraint or ON CONFLICT DO NOTHING |
| TD-03 | Quota Re-Check in Validation Worker | PRD 6.1 | The quota check (50 items/user) is enforced in the API Gateway rather than the Validation Worker. If a user's quota changes between API receipt and validation processing, the worker will still register the product. | Low — Quota is unlikely to change during async processing window |
| TD-04 | Volatility-Based Frequency Scheduling | PRD 6.2 | Scheduler uses a fixed 6-hour interval for all products. Dynamic frequency adjustment based on product popularity or price volatility is not implemented. | Medium — All products consume equal resources regardless of actual need |
| TD-05 | Anomaly Price Sanitization | PRD 6.3 | Absurd price variations (e.g., R$5000 to R$10) are not filtered. Scraping errors or scammer sellers could corrupt the all-time-low metric. | Medium — Could distort decision engine trigger accuracy |
| TD-06 | Affiliate Tag Insertion | PRD 6.5 | Notification URLs do not embed affiliate tags. Revenue monetization via Amazon Associates is not active. | None — Out of MVP scope |
| TD-07 | Monthly Quota Hard Stop | PRD N/A, AGENTS 4 | ~~No monitoring service checks CloudAMQP message consumption (1M/month limit). The Scheduler does not auto-interrupt at 95% threshold.~~ **Implemented**: `CloudAMQPQuotaMonitor` checks the RabbitMQ Management API; Scheduler aborts publishing at 95% and alerts admin via Telegram. | ~~High~~ **Resolved** — Quota hard stop active; monitoring depends on management API availability |
| TD-08 | DLQ Mass Reprocessing | AGENTS 0.2 | Messages in DLQs require manual inspection via RabbitMQ dashboard. No CLI or dashboard for bulk reprocessing exists. | Medium — Operational overhead for failure recovery |
| TD-09 | Worker Unit Test Coverage | AGENTS 5 | ~~Worker business logic had 0% coverage due to complex async mocking of aio-pika context managers~~ **Implemented**: Added 36 unit tests covering Validation, Scraper, Decision, and Notification workers with async mocks; overall coverage reached 64% | ~~High~~ **Resolved** — Worker core logic now covered; scheduler/base worker runtime loops remain as integration targets |