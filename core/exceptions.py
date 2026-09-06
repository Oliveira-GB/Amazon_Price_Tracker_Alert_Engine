class AppException(Exception):
    def __init__(self, message: str, code: str = "APP_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class ParsingError(AppException):
    def __init__(self, message: str, asin: str | None = None):
        self.asin = asin
        super().__init__(message, code="PARSING_ERROR")


class ASINExtractionError(AppException):
    def __init__(self, message: str, url: str | None = None):
        self.url = url
        super().__init__(message, code="ASIN_EXTRACTION_ERROR")


class AmazonBlockError(AppException):
    def __init__(self, message: str = "Amazon blocked the request", status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message, code="AMAZON_BLOCK")


class ProductUnavailableError(AppException):
    def __init__(self, asin: str):
        super().__init__(f"Product {asin} is unavailable", code="PRODUCT_UNAVAILABLE")


class QuotaExceededError(AppException):
    def __init__(self, current_count: int, limit: int):
        self.current_count = current_count
        self.limit = limit
        super().__init__(
            f"Quota exceeded: {current_count}/{limit} products",
            code="QUOTA_EXCEEDED"
        )


class TelegramError(AppException):
    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message, code="TELEGRAM_ERROR")


class UserBlockedError(TelegramError):
    def __init__(self, user_id: str):
        self.user_id = user_id
        super().__init__(f"User {user_id} blocked the bot", status_code=403)


class CooldownActiveError(AppException):
    def __init__(self, user_id: str, asin: str, retry_after_seconds: int):
        self.user_id = user_id
        self.asin = asin
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            f"Cooldown active for user {user_id} on {asin}",
            code="COOLDOWN_ACTIVE"
        )


class CircuitBreakerOpenError(AppException):
    def __init__(self, worker_name: str, wait_seconds: int):
        self.worker_name = worker_name
        self.wait_seconds = wait_seconds
        super().__init__(
            f"Circuit breaker open for {worker_name}, waiting {wait_seconds}s",
            code="CIRCUIT_BREAKER_OPEN"
        )
