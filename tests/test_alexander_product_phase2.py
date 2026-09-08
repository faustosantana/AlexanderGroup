"""Phase 2 catalog tests: 2-decimal money and rematch rules (no Odoo writes)."""

from tools.alexander_product_master.money import (
    has_excess_precision,
    money2,
    money2_float,
)
from tools.alexander_product_master.phase2_build import (
    is_non_product,
    match_existing,
    index_catalog,
)
from tools.alexander_product_master.classify import identity_key, is_service


def test_money_half_up_not_truncate():
    assert str(money2("23539.997")) == "23540.00"
    assert str(money2("2668.126")) == "2668.13"
    assert str(money2("11932.5")) == "11932.50"
    assert str(money2("225")) == "225.00"
    assert str(money2("0")) == "0.00"
    assert money2_float(23539.997) == 23540.0
    assert money2("23539.997") != money2("23539.99")


def test_excess_precision_detect():
    assert has_excess_precision(23539.997)
    assert has_excess_precision(2259.995)
    assert not has_excess_precision(225)
    assert not has_excess_precision(11932.5)
    assert not has_excess_precision(0)


def test_invoice_codes_are_non_products():
    assert is_non_product("FACT-B15-001")
    assert is_non_product("FACT-B15-125")
    assert is_non_product("Preliminares")
    assert is_non_product("Artista")
    assert not is_non_product("Alambre #8 AWG")


def test_identity_does_not_merge_awg():
    assert identity_key("Alambre #8 AWG") != identity_key("Alambre #10 AWG")


def test_match_existing_exact_and_safe():
    catalog = [
        {"id": 1, "name": "CARNE DE RES", "list_price": 225, "uom": "lb"},
        {"id": 2, "name": "Alambre #10 AWG", "list_price": 100, "uom": "Units"},
    ]
    idx = index_catalog(catalog)
    kind, hit = match_existing("Carne de res", idx)
    assert kind == "MATCH_EXISTING_EXACT"
    assert hit["id"] == 1
    kind, hit = match_existing("Alambre #8 AWG", idx)
    assert kind == "NEW_PRODUCT_WITHOUT_PRICE"


def test_transporte_is_service():
    assert is_service("Transporte de materiales")
