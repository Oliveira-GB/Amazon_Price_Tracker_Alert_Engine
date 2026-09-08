import pytest

from api.bot.templates import (
    escape_markdown_v2,
    format_price,
    product_list_template,
    start_template,
    help_template,
    quota_exceeded_template,
    processing_template,
    error_template,
    upgrade_requested_template,
    product_registered_template,
    product_removed_template,
    product_paused_template,
    product_resumed_template,
    truncate,
)


class TestEscapeMarkdownV2:
    def test_escape_asterisk(self):
        assert escape_markdown_v2("hello *world*") == r"hello \*world\*"

    def test_escape_underscore(self):
        assert escape_markdown_v2("hello_world") == r"hello\_world"

    def test_escape_brackets(self):
        assert escape_markdown_v2("[hello]") == r"\[hello\]"

    def test_escape_all_special_chars(self):
        text = "*hello* _world_ [test] (item) ~code~ #tag +plus -minus =equals {brace} .dot !exclaim"
        result = escape_markdown_v2(text)
        assert "\\" in result

    def test_no_special_chars(self):
        assert escape_markdown_v2("hello world 123") == "hello world 123"


class TestTruncate:
    def test_truncate_short_text(self):
        text = "hello world"
        assert truncate(text, 50) == "hello world"

    def test_truncate_long_text(self):
        text = "a" * 300
        result = truncate(text, 50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_truncate_exactly_at_limit(self):
        text = "a" * 50
        assert truncate(text, 50) == text


class TestFormatPrice:
    def test_format_price_with_value(self):
        assert format_price(299.90) == "R$ 299,90"

    def test_format_price_with_none(self):
        assert format_price(None) == "N/A"

    def test_format_price_integer(self):
        assert format_price(300.0) == "R$ 300,00"

    def test_format_price_thousands(self):
        assert format_price(1999.99) == "R$ 1.999,99"


class TestStartTemplate:
    def test_start_template_contains_welcome(self):
        result = start_template()
        assert "Bem-vindo" in result
        assert "/help" in result


class TestHelpTemplate:
    def test_help_template_lists_commands(self):
        result = help_template()
        assert "/start" in result
        assert "/list" in result
        assert "/pause" in result
        assert "/help" in result


class TestQuotaExceededTemplate:
    def test_quota_exceeded_contains_limit(self):
        result = quota_exceeded_template(50)
        assert "50" in result
        assert "Limite" in result or "produtos" in result.lower()


class TestProcessingTemplate:
    def test_processing_template(self):
        result = processing_template()
        assert "Processando" in result or "notificado" in result.lower()


class TestErrorTemplate:
    def test_error_template(self):
        result = error_template("Test error")
        assert "Erro" in result
        assert "Test error" in result


class TestUpgradeRequestedTemplate:
    def test_upgrade_requested_template(self):
        result = upgrade_requested_template()
        assert "solicitação" in result.lower() or "enviada" in result.lower()


class TestProductRegisteredTemplate:
    def test_product_registered_template(self):
        result = product_registered_template("Test Product", "B08ABC1234", 299.90)
        assert "registrado" in result.lower()
        assert "B08ABC1234" in result
        assert "299" in result


class TestProductRemovedTemplate:
    def test_product_removed_template(self):
        result = product_removed_template("Test Product")
        assert "removido" in result.lower() or "excluído" in result.lower()


class TestProductPausedTemplate:
    def test_product_paused_template(self):
        result = product_paused_template("Test Product")
        assert "pausado" in result.lower() or "pausada" in result.lower()


class TestProductResumedTemplate:
    def test_product_resumed_template(self):
        result = product_resumed_template("Test Product")
        assert "ativado" in result.lower() or "retomado" in result.lower()
