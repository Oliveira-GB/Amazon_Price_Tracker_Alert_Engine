from typing import Any

from models.user_product import UserProduct


def product_list_keyboard(
    subscriptions: list[UserProduct],
    page: int = 1,
    per_page: int = 10,
) -> dict[str, Any]:
    keyboard: list[list[dict[str, str]]] = []

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_subs = subscriptions[start_idx:end_idx]

    for sub in page_subs:
        product = sub.product

        if sub.is_active:
            btn_text = f"⏸ Pausar | {product.asin[:6]}"
        else:
            btn_text = f"▶️ Ativar | {product.asin[:6]}"

        keyboard.append(
            [
                {
                    "text": btn_text,
                    "callback_data": f"pause:{product.id}",
                },
                {
                    "text": "🗑 Excluir",
                    "callback_data": f"delete:{product.id}",
                },
            ]
        )

    nav_buttons = []
    if page > 1:
        nav_buttons.append({"text": "◀️ Anterior", "callback_data": f"page:{page - 1}"})
    if len(subscriptions) > end_idx:
        nav_buttons.append({"text": "Próxima ▶️", "callback_data": f"page:{page + 1}"})

    if nav_buttons:
        keyboard.append(nav_buttons)

    return {"inline_keyboard": keyboard}


def confirmation_keyboard(action: str, item_id: str) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Confirmar", "callback_data": f"confirm:{action}:{item_id}"},
                {"text": "❌ Cancelar", "callback_data": f"cancel:{action}:{item_id}"},
            ]
        ]
    }


def pagination_keyboard(
    current_page: int,
    total_pages: int,
) -> dict[str, Any]:
    keyboard: list[list[dict[str, str]]] = []

    nav_buttons = []
    if current_page > 1:
        nav_buttons.append({"text": "◀️ Anterior", "callback_data": f"page:{current_page - 1}"})
    if current_page < total_pages:
        nav_buttons.append({"text": "Próxima ▶️", "callback_data": f"page:{current_page + 1}"})

    if nav_buttons:
        keyboard.append(nav_buttons)

    return {"inline_keyboard": keyboard}
