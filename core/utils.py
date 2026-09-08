import re


def extract_price_from_text(text: str) -> float | None:
    match = re.search(r"[\d.,]+", text.replace(",", "."))
    if match:
        price_str = match.group().replace(",", "")
        try:
            return float(price_str)
        except ValueError:
            return None
    return None
