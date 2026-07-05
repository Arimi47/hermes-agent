from decimal import Decimal
from mfiles_cli.rent_check import rent_check, STATUS_JA, STATUS_NEIN, STATUS_OFFEN


def test_artis_equal_rent_is_ja():
    result = rent_check({"id": 5777, "net_rent": Decimal("1650.00"), "tenant": "Artis"}, "Der Mietzins betraegt 1.650,00 EUR netto.", "vertrag")
    assert result["status"] == STATUS_JA


def test_mama_pizza_delta_is_nein():
    result = rent_check({"id": 5778, "net_rent": Decimal("1693.73"), "tenant": "Mama Pizza"}, "ab 15.01.2024 betraegt die Staffelmiete 1.674,75 EUR", "vertrag")
    assert result["status"] == STATUS_NEIN
    assert result["delta"] == Decimal("18.98")


def test_no_docs_is_offen():
    result = rent_check({"id": 5816, "net_rent": Decimal("1000.00")}, "", "")
    assert result["status"] == STATUS_OFFEN


def test_index_clause_prevents_blind_ja():
    text = "ab 01.01.2025 7.000,00 EUR. Ab dem 01.01.2026 wird die Miete automatisch nach Verbraucherpreisindex angepasst."
    result = rent_check({"id": 5814, "net_rent": Decimal("7000.00")}, text, "3. Nachtrag")
    assert result["status"] in {STATUS_NEIN, STATUS_OFFEN}
    assert "Index" in result["source"] or "VPI" in result["source"]
