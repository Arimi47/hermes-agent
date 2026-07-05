from decimal import Decimal
from mfiles_cli.formatters import parse_amount, money


def test_german_amounts():
    assert parse_amount("7.000,00 €") == Decimal("7000.00")
    assert parse_amount("1.674,75") == Decimal("1674.75")
    assert parse_amount("3212,50€") == Decimal("3212.50")


def test_dm_is_not_blindly_eur():
    assert parse_amount("DM 1.650,--") is None


def test_money_format():
    assert money(Decimal("7000")) == "7.000,00 €"
