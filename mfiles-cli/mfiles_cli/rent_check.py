import re
from decimal import Decimal
from typing import Any

from .formatters import parse_amount, money

STATUS_JA = "JA"
STATUS_NEIN = "NEIN"
STATUS_OFFEN = "OFFEN"


def infer_contract_rent(text: str) -> tuple[Decimal | None, str, str, str]:
    """Conservative heuristic parser for first CLI version."""
    if not text.strip():
        return None, "", "", "kein extrahierter Vertragstext"
    date_amount = re.findall(r"(?is)(?:ab|zum|seit)\s*(\d{1,2}\.\d{1,2}\.\d{4}).{0,120}?([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})\s*(?:€|EUR)?", text)
    if date_amount:
        date, amount = sorted(date_amount, key=lambda x: x[0])[-1]
        return parse_amount(amount), date, "vertragliche/staffelmaessige Miete", f"Betrag in Naehe von Datum {date}"
    amount_patterns = [
        r"(?is)(?:nettokaltmiete|kaltmiete|mietzins|grundmiete|nettomiete).{0,80}?([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})\s*(?:€|EUR)?",
        r"(?is)([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})\s*(?:€|EUR).{0,40}?(?:nettokaltmiete|kaltmiete|mietzins|grundmiete|nettomiete)",
    ]
    for pat in amount_patterns:
        m = re.search(pat, text)
        if m:
            return parse_amount(m.group(1)), "", "Vertragsmiete", "Mietzins-/Kaltmiete-Klausel"
    return None, "", "", "kein belastbarer Mietbetrag erkannt"


def has_index_adjustment(text: str) -> bool:
    return bool(
        re.search(r"(?is)(index|verbraucherpreis|vpi|preisindex|indexstand).{0,200}(anpass|erhöh|erhoeh|jaehrlich|jährlich|automatisch)", text)
        or re.search(r"(?is)(anpass|erhöh|erhoeh|jaehrlich|jährlich|automatisch).{0,200}(index|verbraucherpreis|vpi|preisindex|indexstand)", text)
    )


def rent_check(unit: dict[str, Any], contract_text: str, source: str = "") -> dict[str, Any]:
    mfiles_rent = parse_amount(unit.get("net_rent"))
    contract_rent, basis_date, date_kind, note = infer_contract_rent(contract_text)
    status = STATUS_OFFEN
    delta = None
    klartext = "Kein belastbarer Vertrag/Beleg gefunden. Manuelle Pruefung noetig."
    if mfiles_rent is not None and contract_rent is not None:
        delta = mfiles_rent - contract_rent
        status = STATUS_JA if abs(delta) < Decimal("0.01") else STATUS_NEIN
        klartext = f"M-Files zeigt {money(mfiles_rent)}; Vertrag/Beleg zeigt {money(contract_rent)}."
    if has_index_adjustment(contract_text):
        if status == STATUS_JA:
            status = STATUS_OFFEN
        note = (note + "; " if note else "") + "Index-/VPI-Klausel erkannt - aktuelle Anpassung rechnerisch pruefen"
        klartext += " Es wurde eine Index-/VPI-Klausel erkannt; die aktuelle automatische Anpassung muss gegen den relevanten Indexstand geprueft werden."
    source_text = source
    if note:
        source_text = f"{source}; {note}" if source else note
    return {
        "unit_id": unit.get("id"),
        "unit": unit.get("unit_name") or unit.get("unit_number") or unit.get("bezeichnung") or "",
        "tenant": unit.get("tenant", ""),
        "mfiles_net_rent": mfiles_rent,
        "contract_or_evidence_rent": contract_rent,
        "delta": delta,
        "status": status,
        "basis_date": basis_date,
        "date_kind": date_kind,
        "source": source_text,
        "klartext": klartext,
    }
