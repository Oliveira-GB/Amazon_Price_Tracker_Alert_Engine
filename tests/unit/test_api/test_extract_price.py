
from core.utils import extract_price_from_text


class TestExtractPrice:
    def test_extract_price_with_comma(self):
        result = extract_price_from_text("R$ 299,90")
        assert result == 299.90

    def test_extract_price_with_dot(self):
        result = extract_price_from_text("R$ 299.90")
        assert result == 299.90

    def test_extract_price_in_text(self):
        result = extract_price_from_text("Check price: 150.50 now!")
        assert result == 150.50

    def test_extract_price_no_price(self):
        result = extract_price_from_text("hello world")
        assert result is None

    def test_extract_price_invalid(self):
        result = extract_price_from_text("abc")
        assert result is None

    def test_extract_price_only_comma(self):
        result = extract_price_from_text("299,")
        assert result == 299.0

    def test_extract_price_with_spaces(self):
        result = extract_price_from_text("299 . 90")
        assert result == 299.0

    def test_extract_price_multiple_prices(self):
        result = extract_price_from_text("Original: 100.00")
        assert result == 100.00

    def test_extract_price_leading_text(self):
        result = extract_price_from_text("The price is 49.99 only")
        assert result == 49.99

    def test_extract_price_trailing_text(self):
        result = extract_price_from_text("49.99 this is the price")
        assert result == 49.99
