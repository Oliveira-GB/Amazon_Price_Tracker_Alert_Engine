from unittest.mock import MagicMock

import pytest


class MockProduct:
    def __init__(self, asin="B08ABC1234", title="Test Product"):
        self.id = "550e8400-e29b-41d4-a716-446655440000"
        self.asin = asin
        self.title = title


class MockUserProduct:
    def __init__(self, is_active=True):
        self.is_active = is_active
        self.product = MockProduct()


class TestProductListKeyboard:
    def test_empty_subscriptions(self):
        from api.bot.keyboards import product_list_keyboard

        keyboard = product_list_keyboard([])
        assert "inline_keyboard" in keyboard
        assert len(keyboard["inline_keyboard"]) == 0

    def test_single_subscription_active(self):
        from api.bot.keyboards import product_list_keyboard

        mock_sub = MockUserProduct(is_active=True)
        keyboard = product_list_keyboard([mock_sub])

        assert len(keyboard["inline_keyboard"]) == 1
        buttons = keyboard["inline_keyboard"][0]
        assert len(buttons) == 2
        assert "Pausar" in buttons[0]["text"]

    def test_single_subscription_inactive(self):
        from api.bot.keyboards import product_list_keyboard

        mock_sub = MockUserProduct(is_active=False)
        keyboard = product_list_keyboard([mock_sub])

        buttons = keyboard["inline_keyboard"][0]
        assert "Ativar" in buttons[0]["text"]

    def test_multiple_subscriptions(self):
        from api.bot.keyboards import product_list_keyboard

        mock_subs = [MockUserProduct() for _ in range(3)]
        keyboard = product_list_keyboard(mock_subs)

        assert len(keyboard["inline_keyboard"]) == 3

    def test_pagination_first_page(self):
        from api.bot.keyboards import product_list_keyboard

        mock_subs = [MockUserProduct() for _ in range(15)]
        keyboard = product_list_keyboard(mock_subs, page=1, per_page=10)

        rows = keyboard["inline_keyboard"]
        assert len(rows) == 11
        assert "◀️ Anterior" not in rows[-1][0]["text"]
        assert "Próxima ▶️" in rows[-1][0]["text"]

    def test_pagination_last_page(self):
        from api.bot.keyboards import product_list_keyboard

        mock_subs = [MockUserProduct() for _ in range(15)]
        keyboard = product_list_keyboard(mock_subs, page=2, per_page=10)

        rows = keyboard["inline_keyboard"]
        nav_row = rows[-1]
        nav_texts = [btn["text"] for btn in nav_row]
        assert "◀️ Anterior" in nav_texts
        assert "Próxima ▶️" not in nav_texts

    def test_pagination_middle_of_three_pages(self):
        from api.bot.keyboards import product_list_keyboard

        mock_subs = [MockUserProduct() for _ in range(25)]
        keyboard = product_list_keyboard(mock_subs, page=2, per_page=10)

        rows = keyboard["inline_keyboard"]
        nav_row = rows[-1]
        nav_texts = [btn["text"] for btn in nav_row]
        assert "◀️ Anterior" in nav_texts
        assert "Próxima ▶️" in nav_texts


class TestConfirmationKeyboard:
    def test_confirmation_keyboard_structure(self):
        from api.bot.keyboards import confirmation_keyboard

        keyboard = confirmation_keyboard("delete", "item-123")

        assert "inline_keyboard" in keyboard
        row = keyboard["inline_keyboard"][0]
        assert len(row) == 2
        assert "Confirmar" in row[0]["text"]
        assert "Cancelar" in row[1]["text"]

    def test_confirmation_callback_data(self):
        from api.bot.keyboards import confirmation_keyboard

        keyboard = confirmation_keyboard("delete", "item-123")

        row = keyboard["inline_keyboard"][0]
        assert row[0]["callback_data"] == "confirm:delete:item-123"
        assert row[1]["callback_data"] == "cancel:delete:item-123"


class TestPaginationKeyboard:
    def test_pagination_keyboard_single_page(self):
        from api.bot.keyboards import pagination_keyboard

        keyboard = pagination_keyboard(1, 1)
        assert keyboard["inline_keyboard"] == []

    def test_pagination_keyboard_has_previous(self):
        from api.bot.keyboards import pagination_keyboard

        keyboard = pagination_keyboard(2, 3)

        rows = keyboard["inline_keyboard"]
        assert len(rows) == 1
        assert "◀️ Anterior" in rows[0][0]["text"]

    def test_pagination_keyboard_has_next(self):
        from api.bot.keyboards import pagination_keyboard

        keyboard = pagination_keyboard(1, 3)

        rows = keyboard["inline_keyboard"]
        assert len(rows) == 1
        assert "Próxima ▶️" in rows[0][0]["text"]

    def test_pagination_keyboard_has_both(self):
        from api.bot.keyboards import pagination_keyboard

        keyboard = pagination_keyboard(2, 3)

        rows = keyboard["inline_keyboard"]
        assert len(rows) == 1
        assert len(rows[0]) == 2
