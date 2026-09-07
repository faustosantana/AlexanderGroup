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


def test_ncf_excel_plan_has_34_rows_and_ignores_doralex_b01_b15_typo():
    from tools.alexander_operational_readiness.ncf_excel_plan import (
        EXCEL_NCF_ROWS,
        plan_range,
    )

    assert len(EXCEL_NCF_ROWS) == 34
    b01 = next(
        r
        for r in EXCEL_NCF_ROWS
        if r["company"].startswith("INVERSIONES DORALEX")
        and r["declared_type"] == "B01"
    )
    planned = plan_range(b01, max_historical_seq=53)
    assert planned["start"] == 52
    assert planned["end"] == 87
    assert planned["next"] == 54
    assert any("EXCEL_NEXT_PREFIX_IGNORED" in n for n in planned["notes"])


def test_ncf_excel_plan_expired_keeps_excel_date_and_blu_b15_uses_excel_next():
    from tools.alexander_operational_readiness.ncf_excel_plan import (
        EXCEL_NCF_ROWS,
        plan_range,
    )

    pin_b01 = next(
        r
        for r in EXCEL_NCF_ROWS
        if "PIÑARIA" in r["company"] and r["declared_type"] == "B01"
    )
    planned = plan_range(pin_b01)
    assert planned["next"] == 9
    assert planned["date_to"] == "2025-12-31"
    assert any("ya pasó" in n for n in planned["notes"])
    na_row = next(
        r
        for r in EXCEL_NCF_ROWS
        if r["company"].startswith("INVERSIONES DORALEX")
        and r["declared_type"] == "B02"
    )
    assert plan_range(na_row)["date_to"] == "2099-12-31"
    blu = next(
        r
        for r in EXCEL_NCF_ROWS
        if r["company"].startswith("BLUE ELITE") and r["declared_type"] == "B15"
    )
    planned = plan_range(blu)
    assert planned["next"] == 102
    assert planned["end"] == 102
    assert planned["excel_end"] == 20


def test_ncf_assignment_expired_message_is_explicit():
    from pathlib import Path

    src = Path("addons/alexander/justech_alexander_base/models/ncf_assignment.py")
    text = src.read_text(encoding="utf-8")
    assert "está vencido" in text
    assert "No se puede facturar hasta validarlo" in text


def test_opening_baseline_constants_unchanged():
    assert BATCH == "ALEXANDER_OPENING_2026-09-04"
    assert EXPECTED_AR == "27240211.80"
    assert EXPECTED_PDFS == 26
    assert EXPECTED_MISSING_PDF == "B1300000016"
