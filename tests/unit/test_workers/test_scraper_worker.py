

from workers.scraper.consumer import CircuitBreaker, extract_price


class TestExtractPrice:
    def test_extract_price_with_comma(self):
        text = "R$ 299,90"
        result = extract_price(text)
        assert result == 299.90

    def test_extract_price_with_dot(self):
        text = "R$ 299.90"
        result = extract_price(text)
        assert result == 299.90

    def test_extract_price_no_match(self):
        text = "no price here"
        result = extract_price(text)
        assert result is None

    def test_extract_price_complex_format(self):
        text = "De: R$ 599,90 Por: R$ 399,90"
        result = extract_price(text)
        assert result is not None


class TestCircuitBreaker:
    def test_circuit_breaker_initial_closed(self):
        cb = CircuitBreaker(threshold=5, timeout=120)
        assert cb.is_open() is False
        assert cb.failures == 0

    def test_circuit_breaker_opens_after_threshold(self):
        cb = CircuitBreaker(threshold=3, timeout=120)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open() is False
        cb.record_failure()
        assert cb.is_open() is True
        assert cb.failures == 3

    def test_circuit_breaker_resets_on_success(self):
        cb = CircuitBreaker(threshold=3, timeout=120)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.failures == 0
        assert cb.is_open() is False

    def test_circuit_breaker_recovery_after_timeout(self):
        from datetime import timedelta

        cb = CircuitBreaker(threshold=1, timeout=1)
        cb.record_failure()
        assert cb.is_open() is True

        cb.opened_at = cb.opened_at - timedelta(seconds=2)
        assert cb.is_open() is False
        assert cb.failures == 0

    def test_circuit_breaker_multiple_failures(self):
        cb = CircuitBreaker(threshold=5, timeout=120)
        for _ in range(4):
            cb.record_failure()
        assert cb.is_open() is False
        cb.record_failure()
        assert cb.is_open() is True
