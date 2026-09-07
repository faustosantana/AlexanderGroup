"""Pruebas de estructura del paquete de readiness (sin Odoo)."""

from tools.alexander_operational_readiness.excel_source import (
    BATCH,
    EXCEL_BANKS,
    EXCEL_COMPANIES,
    EXPECTED_AR,
    EXPECTED_MISSING_PDF,
    EXPECTED_PDFS,
)


def test_excel_source_has_six_operating_companies():
    assert len(EXCEL_COMPANIES) == 6
    rncs = {c["rnc"] for c in EXCEL_COMPANIES}
    assert rncs == {
        "132220112",
        "132271068",
        "132721502",
        "132710152",
        "132769155",
        "133371261",
    }


def test_excel_banks_match_companies_and_invalid_date_is_preserved():
    assert len(EXCEL_BANKS) == 6
    assert {b["number"] for b in EXCEL_BANKS} == {
        "9604436830",
        "9604097492",
        "9605588726",
        "9605543104",
        "9608739498",
        "9608670542",
    }
    assert all(b["balance_date"] == "05//08/2026" for b in EXCEL_BANKS)


def test_opening_baseline_constants_unchanged():
    assert BATCH == "ALEXANDER_OPENING_2026-09-04"
    assert EXPECTED_AR == "27240211.80"
    assert EXPECTED_PDFS == 26
    assert EXPECTED_MISSING_PDF == "B1300000016"
