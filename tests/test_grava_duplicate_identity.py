"""The two Grava 3/4 opening names must share one identity key."""

from tools.alexander_product_master.classify import identity_key
from tools.alexander_product_master.textutil import collapse


def test_grava_parentheses_are_same_product():
    a = "(AGREGADO GRUESO) GRAVA 3/4"
    b = "AGREGADO GRUESO (GRAVA) 3/4"
    assert collapse(a) == collapse(b) == "agregado grueso grava 3/4"
    assert identity_key(a) == identity_key(b)


def test_grava_range_stays_distinct():
    assert identity_key("GRAVA 3/4 A 1/2") != identity_key(
        "AGREGADO GRUESO (GRAVA) 3/4"
    )
    assert identity_key("GRAVA 3/4 A 1/2") != identity_key("GRAVA 3/4")


def test_grava_caliza_and_supplier_stay_distinct():
    base = identity_key("AGREGADO GRUESO (GRAVA) 3/4")
    assert identity_key("AGREGADO GRUESO (GRAVA CALIZA) 3/4") != base
    assert identity_key("AGREGADO GRUESO (GRAVA) 3/4 KHOURY/GRUPO ALTERRA") != base
