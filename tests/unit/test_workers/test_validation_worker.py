

from workers.validation.consumer import extract_asins_from_text


class TestExtractAsinsFromText:
    def test_valid_url_amazon_br(self):
        text = "https://www.amazon.com.br/dp/B08ABC1234"
        asins = extract_asins_from_text(text)
        assert "B08ABC1234" in asins

    def test_valid_url_amazon_com(self):
        text = "https://www.amazon.com/dp/B08XYZ9876"
        asins = extract_asins_from_text(text)
        assert "B08XYZ9876" in asins

    def test_short_link_no_asin(self):
        text = "https://amzn.to/xyz"
        asins = extract_asins_from_text(text)
        assert len(asins) == 0

    def test_affiliate_url_with_params(self):
        text = "https://www.amazon.com.br/dp/B08ABC1234?ref=cm_sw_r_ud_dp_ABC123&linkCode=ll1&tag=name-20"
        asins = extract_asins_from_text(text)
        assert "B08ABC1234" in asins

    def test_multiple_urls_returns_unique(self):
        text = "Check https://amazon.com/dp/B08ABC1234 and https://amazon.com/dp/B08ABC1234"
        asins = extract_asins_from_text(text)
        assert len(asins) == 1
        assert "B08ABC1234" in asins

    def test_no_asin_found(self):
        text = "hello world"
        asins = extract_asins_from_text(text)
        assert len(asins) == 0

    def test_asin_in_gp_product_format(self):
        text = "https://www.amazon.com/gp/product/B08ABC1234"
        asins = extract_asins_from_text(text)
        assert "B08ABC1234" in asins

    def test_asin_in_gp_aw_d_format(self):
        text = "https://www.amazon.com/gp/aw/d/B08ABC1234"
        asins = extract_asins_from_text(text)
        assert "B08ABC1234" in asins

    def test_lowercase_asin(self):
        text = "https://www.amazon.com/dp/b08abc1234"
        asins = extract_asins_from_text(text)
        assert "b08abc1234" in asins

    def test_url_with_multiple_asins_not_common(self):
        text = "First: https://amazon.com/dp/B08ABC1234 then https://amazon.com/dp/C08XYZ9876"
        asins = extract_asins_from_text(text)
        assert len(asins) >= 1

    def test_asin_with_numbers_only(self):
        text = "https://www.amazon.com/dp/1234567890"
        asins = extract_asins_from_text(text)
        assert "1234567890" in asins
