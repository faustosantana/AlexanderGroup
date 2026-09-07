"""Unit tests for the Alexander product master catalog builder (no Odoo writes)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from tools.alexander_product_master.classify import (
    category_for,
    document_type,
    extract_specs,
    identity_key,
    is_food,
    is_meat,
    is_service,
    map_uom,
)
from tools.alexander_product_master.extract import SOURCE_DIR, source_files
from tools.alexander_product_master.group_match import (
    decide_action,
    enrich,
    group_rows,
    match_odoo,
)
from tools.alexander_product_master.prices import pick_max_price, unit_price_excl_tax
from tools.alexander_product_master.textutil import is_admin_text


def test_exact_duplicate_files_detected_by_hash():
    unique, skipped = source_files(SOURCE_DIR)
    assert len(unique) + len(skipped) == 16
    assert len(skipped) == 4
    unique_hashes = {u["sha256"] for u in unique}
    for rec in skipped:
        assert rec["sha256"] in unique_hashes
    # No pair is imported twice.
    names = [u["name"] for u in unique] + [s["name"] for s in skipped]
    assert len(names) == 16


def test_admin_rows_are_not_products():
    for text in (
        "SUBTOTAL",
        "Total General",
        "ITBIS 18%",
        "Forma de pago",
        "RNC",
        "Cliente:",
        "Observaciones",
        "Firma",
    ):
        assert is_admin_text(text), text


def test_food_excludes_paint_and_machine_oil():
    assert not is_food("PASTA ACRÍLICA BLANCA 5 GAL")
    assert not is_food("ACEITE 3 EN 1")
    assert not is_food("ACEITE HIDRAULICO")
    assert is_food("ARROZ SELECTO 50 LB")
    assert is_food("ACEITE COMESTIBLE 1 GAL")
    assert is_meat("CARNE DE RES DESHUESADA")
    assert is_meat("CHULETA DE CERDO")
    assert not is_meat("PASTA ACRÍLICA")


def test_service_excludes_valvula_de_servicio():
    assert not is_service("Válvula de servicio 1/2")
    assert is_service("Limpieza de séptico y sondeo de tubería")
    assert is_service("Montaje de eventos artísticos")
    assert is_service("Instalación de puerta")
    assert is_service("Mano de obra")


def test_identity_does_not_overmerge_sizes():
    assert identity_key('TV TCL 32"') != identity_key('TV TCL 43"')
    assert identity_key("VARILLA 3/8") != identity_key("VARILLA 1/2")
    assert identity_key("NEVERA MIDEA 10 PIES") != identity_key("NEVERA MIDEA 12 PIES")
    assert identity_key("TONER 26A") != identity_key("TONER 26X")
    assert identity_key("PINTURA BLANCA") != identity_key("PINTURA ROJA")
    assert identity_key("CEMENTO 42.5 KG") != identity_key("CEMENTO 94 LB")


def test_identity_does_undermerge_spelling():
    a = identity_key("Cemento Gris Santo Domingo 94 LB")
    b = identity_key("CEMENTO GRIS SANTO DOMINGO 94LB")
    c = identity_key("cemento gris santo domingo 94 lbs")
    assert a == b == c


def test_price_reconcile_qty_times_unit():
    price, status = unit_price_excl_tax(
        {
            "document_type": "QUOTATION",
            "quantity": 4,
            "raw_unit_price": 100,
            "subtotal": 400,
            "total": 472,
            "itbis": 72,
        }
    )
    assert price == 100
    assert "RECONCILED" in status


def test_price_does_not_use_line_total_as_unit():
    price, status = unit_price_excl_tax(
        {
            "document_type": "QUOTATION",
            "quantity": 4,
            "raw_unit_price": 400,
            "subtotal": 400,
            "total": 472,
        }
    )
    assert price is None
    assert status == "PRICE_COLUMN_AMBIGUOUS"


def test_cost_analysis_never_becomes_sale_price():
    price, status = unit_price_excl_tax(
        {
            "document_type": "COST_ANALYSIS",
            "quantity": 1,
            "raw_unit_price": 8500,
        }
    )
    assert price is None
    assert status == "COST_NOT_SALE_PRICE"


def test_outlier_blocked_but_single_high_price_kept():
    price, rule = pick_max_price([500, 525, 550, 55000])
    assert price is None
    assert rule == "PRICE_OUTLIER_REVIEW"
    price, rule = pick_max_price([8500, 9300, 10200])
    assert price == 10200
    assert rule == "MAX"


def test_uom_normalization():
    assert map_uom("UND") == "Units"
    assert map_uom("UD") == "Units"
    assert map_uom("Unidad") == "Units"
    assert map_uom("GALÓN") == "Gal"
    assert map_uom("LB") == "lb"


def test_category_food_and_shared():
    assert category_for("Carne de res", False, False, True) == "Carnes"
    assert category_for("Arroz 50 lb", False, True, False) == "Alimentos"
    assert category_for("Taladro DeWalt 1/2", False, False, False) == "Herramientas"
    assert category_for("Limpieza de séptico", True, False, False) == "Servicios"


def test_services_collapse_to_one_group():
    rows = [
        enrich(
            {
                "source_file": "a.xlsx",
                "source_sheet": "s",
                "source_row": 1,
                "document_type": "QUOTATION",
                "raw_description": "Limpieza de séptico",
                "quantity": 1,
                "uom_raw": "UND",
                "raw_unit_price": 76000,
                "price_excl_hint": None,
                "itbis": None,
                "subtotal": 76000,
                "total": 76000,
                "currency": "DOP",
            }
        ),
        enrich(
            {
                "source_file": "b.xlsx",
                "source_sheet": "s",
                "source_row": 2,
                "document_type": "QUOTATION",
                "raw_description": "Montaje de eventos artísticos",
                "quantity": 1,
                "uom_raw": "UND",
                "raw_unit_price": 2500000,
                "price_excl_hint": None,
                "itbis": None,
                "subtotal": 2500000,
                "total": 2500000,
                "currency": "DOP",
            }
        ),
    ]
    groups = group_rows(rows)
    assert len(groups) == 1
    groups = match_odoo(groups, [])
    decided = decide_action(groups[0])
    assert decided["canonical_name"] == "Servicios profesionales"
    assert decided["final_list_price"] == 0.0
    assert decided["action"] == "MAP_TO_SERVICIOS_PROFESIONALES"


def test_existing_price_never_decreases():
    group = {
        "is_service": False,
        "price_rule": "MAX",
        "rows": [{"price_status": "RECONCILED_SUBTOTAL"}],
        "match_type": "EXACT_MATCH",
        "odoo": {"name": "Cemento", "list_price": 10200},
        "historical_max": 8500,
        "company_scope": "SHARED",
    }
    decided = decide_action(group)
    assert decided["final_list_price"] == 10200
    assert decided["action"] == "REUSE_NO_CHANGE"


def test_document_type_cost_vs_quote():
    assert (
        document_type("ANALISIS DE COSTO", "costo unitario volumen") == "COST_ANALYSIS"
    )
    assert document_type("COT-001", "cotizacion cliente") == "QUOTATION"
    assert document_type("CONDUCE", "conduce no. 12") == "DELIVERY"
