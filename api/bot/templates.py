from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.user_product import UserProduct


def escape_markdown_v2(text: str) -> str:
    special_chars = [
        "_", "*", "[", "]", "(", ")", "~", "`", ">",
        "#", "+", "-", "=", "|", "{", "}", ".", "!",
    ]
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text


def truncate(text: str, max_length: int = 200) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def format_price(price: float | None) -> str:
    if price is None:
        return "N/A"
    return f"R$ {price:_.2f}".replace(".", ",").replace("_", ".")


def start_template() -> str:
    return (
        "*Bem-vindo ao Amazon Price Tracker!*\n\n"
        "Aqui você pode rastrear preços de produtos da Amazon e receber alertas "
        "quando o preço cair.\n\n"
        "*Como usar:*\n"
        "1️⃣ Envie um link de produto da Amazon\n"
        "2️⃣ Opcionalmente, envie um preço alvo (ex: `299.90`)\n"
        "3️⃣ Receba notificações quando o preço baixar!\n\n"
        "Use /help para ver todos os comandos."
    )


def help_template() -> str:
    return (
        "*Comandos disponíveis:*\n\n"
        "/start - Iniciar o bot\n"
        "/list - Ver produtos rastreados\n"
        "/pause - Pausar alertas de um produto\n"
        "/delete - Remover um produto\n"
        "/help - Mostrar esta ajuda\n\n"
        "*Como rastrear um produto:*\n"
        "Envie um link da Amazon e, opcionalmente, o preço alvo.\n"
        "Exemplo: `https://amazon.com.br/dp/B08ABC1234 299.90`"
    )


def product_list_template(
    subscriptions: list["UserProduct"],
    user_quota: int,
    page: int = 1,
    per_page: int = 10,
) -> tuple[str, int]:
    total = len(subscriptions)
    if total == 0:
        return (
            "Você ainda não tem produtos rastreados.\n\n"
            "Envie um link da Amazon para começar!",
            1,
        )

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_subs = subscriptions[start_idx:end_idx]
    total_pages = (total + per_page - 1) // per_page

    header = f"Você está rastreando {total}/{user_quota} produtos:\n\n"
    lines = []

    for i, sub in enumerate(page_subs, start=start_idx + 1):
        product = sub.product
        title = truncate(product.title or f"ASIN: {product.asin}", 50)
        title_escaped = escape_markdown_v2(title)

        current_price = product.last_price_discount or product.last_price_full
        price_str = format_price(current_price)

        target_str = ""
        if sub.target_price:
            target_str = f" | Alvo: {format_price(sub.target_price)}"

        status_icon = "⏸" if not sub.is_active else "✅"
        lines.append(
            f"{status_icon} *{i}.* {title_escaped}\n"
            f"   Preço: {price_str}{target_str}"
        )

    body = "\n\n".join(lines)

    footer = ""
    if total_pages > 1:
        footer = f"\n\n📄 Página {page}/{total_pages}"

    return header + body + footer, total_pages


def product_registered_template(title: str, asin: str, target_price: float | None) -> str:
    title_escaped = escape_markdown_v2(truncate(title, 100))
    msg = "✅ *Produto registrado!*\n\n"
    msg += f"{title_escaped}\n"
    msg += f"ASIN: `{asin}`\n"
    if target_price:
        msg += f"Preço alvo: {format_price(target_price)}\n"
    msg += "\nVocê receberá uma notificação quando o preço cair! 🎉"
    return msg


def product_removed_template(title: str) -> str:
    title_escaped = escape_markdown_v2(truncate(title, 100))
    return f"🗑 *Produto removido*\n\n{title_escaped}\n\nNão estará mais rastreando este produto."


def product_paused_template(title: str) -> str:
    title_escaped = escape_markdown_v2(truncate(title, 100))
    return f"⏸ *Produto pausado*\n\n{title_escaped}\n\nUse /list para retomar."


def product_resumed_template(title: str) -> str:
    title_escaped = escape_markdown_v2(truncate(title, 100))
    return f"▶️ *Produto ativado*\n\n{title_escaped}\n\nVocê receberá alertas normalmente."


def quota_exceeded_template(quota: int) -> str:
    return (
        f"⚠️ *Limite de produtos atingido*\n\n"
        f"Você alcançou o limite de {quota} produtos rastreados.\n"
        "Use /delete para remover algum produto ou /request_upgrade para solicitar um aumento."
    )


def processing_template() -> str:
    return "⏳ *Processando...*\n\nVocê será notificado quando o produto for registrado."


def error_template(error_msg: str) -> str:
    error_escaped = escape_markdown_v2(error_msg)
    return f"❌ *Erro*\n\n{error_escaped}\n\nTente novamente ou use /help."


def upgrade_requested_template() -> str:
    return (
        "✅ *Solicitação enviada!*\n\n"
        "Um administrador irá analisar sua solicitação em breve."
    )


def admin_upgrade_request_template(user_chat_id: str, current_count: int, max_quota: int) -> str:
    return (
        "📬 *Nova solicitação de upgrade*\n\n"
        f"Chat ID: `{user_chat_id}`\n"
        f"Produtos atuais: {current_count}/{max_quota}\n\n"
        "Para aumentar a quota, use o painel de administração."
    )


def confirmation_template(action: str, item: str) -> str:
    action_escaped = escape_markdown_v2(action)
    item_escaped = escape_markdown_v2(item)
    return f"⚠️ Tem certeza que deseja {action_escaped}?\n\n{item_escaped}"


def callback_ack_template(message: str) -> str:
    return escape_markdown_v2(message)
