import json
from decimal import Decimal, InvalidOperation
from typing import Any, Sequence


def parse_amount(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = str(value).strip().replace("€", "").replace("EUR", "").replace("\xa0", " ")
    text = text.replace(" ", "")
    if not text:
        return None
    if text.upper().startswith("DM"):
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    text = text.replace("--", "00")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def money(value: Any) -> str:
    amount = parse_amount(value)
    if amount is None:
        return ""
    q = amount.quantize(Decimal("0.01"))
    s = f"{q:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} €"


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def table(rows: Sequence[Sequence[Any]], headers: Sequence[str]) -> str:
    str_rows = [["" if c is None else str(c) for c in row] for row in rows]
    all_rows = [list(headers)] + str_rows
    widths = [max(len(row[i]) for row in all_rows) for i in range(len(headers))]
    def fmt(row):
        return " | ".join(str(row[i]).ljust(widths[i]) for i in range(len(headers)))
    return "\n".join([fmt(headers), "-+-".join("-" * w for w in widths), *[fmt(r) for r in str_rows]])
