"""Pruebas de estructura del importador de apertura (sin Odoo)."""

from decimal import Decimal
from pathlib import Path

from tools.alexander_opening_import.match import match_invoices
from tools.alexander_opening_import.normalize import money, norm_ncf, norm_vat
from tools.alexander_opening_import.parse_excel import parse_workbook
from tools.alexander_opening_import.scan_catalog import (
    REMPART_106_LINES,
    rempart_106_subtotal,
)


def test_vat_and_ncf_normalize():
    assert norm_vat("430-41033-2") == "430410332"
    assert norm_ncf("B1500000147") == "B1500000147"
    assert money("2,763,970.00") == Decimal("2763970.00")


def test_excel_populated_rows_only():
    uploads = Path(
        "/home/ubuntu/.cursor/projects/workspace/uploads/Plantilla_PENDIENTES_Alexander_Odoo_1e80.xlsx"
    )
    if not uploads.exists():
        return
    data = parse_workbook(uploads)
    assert data["users"] == []
    assert data["cxp"] == []
    assert data["fixed_assets"] == []
    assert len(data["cxc"]) == 27
    assert all(r["balance_ok"] for r in data["cxc"])


def test_rempart_106_line_sum():
    assert len(REMPART_106_LINES) == 79
    assert rempart_106_subtotal() == Decimal("1942881.83")


def test_match_blocks_total_mismatch():
    cxc = [
        {
            "company": "INVERSIONES DORALEX,S.RL.",
            "ncf": "B1500000150",
            "vat": "430128368",
            "amount_original": "249754.56",
            "balance_ok": True,
        }
    ]
    pdf = [
        {
            "company": "INVERSIONES DORALEX,S.RL.",
            "ncf": "B1500000150",
            "customer_vat": "430128368",
            "total": "294754.56",
        }
    ]
    result = match_invoices(cxc, pdf)
    assert result["blocked"][0]["EXCEL_PDF_MATCH"] == "FAIL"
