"""Pruebas de estructura del importador de apertura (sin Odoo)."""

from decimal import Decimal
from pathlib import Path

from tools.alexander_opening_import.import_helpers import (
    commercial_partner_fix_vals,
    commercial_partner_vals,
    is_opening_clearing_account,
    resolve_pdf_path,
)
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


def test_commercial_partner_vals_satisfy_has_rnc_preconditions():
    fields = {
        "justech_do_partner_id_type",
        "justech_do_fiscal_config_state",
        "justech_do_fiscal_config_source",
        "justech_do_default_document_type_id",
        "l10n_do_dgii_tax_payer_type",
    }
    vals = commercial_partner_vals(
        "DIRECCION DE INFRAESTRUCTURA ESCOLAR (DIE)",
        "430410332",
        62,
        batch="ALEXANDER_OPENING_2026-09-04",
        doc_type_id=3,
        field_names=fields,
    )
    assert vals["is_company"] is True
    assert vals["company_type"] == "company"
    assert vals["vat"] == "430410332"
    assert vals["country_id"] == 62
    assert vals["justech_do_partner_id_type"] == "1"
    assert "email" not in vals
    assert "phone" not in vals
    assert "street" not in vals


def test_commercial_partner_fix_promotes_individual_to_company():
    vals = commercial_partner_fix_vals(
        {
            "is_company": False,
            "vat_digits": "430410332",
            "justech_do_fiscal_config_state": "pending_new",
            "justech_do_default_document_type_id": None,
            "justech_do_partner_id_type": "2",
            "_doc_type_id": 9,
        },
        {
            "justech_do_fiscal_config_state",
            "justech_do_default_document_type_id",
            "justech_do_partner_id_type",
        },
    )
    assert vals["is_company"] is True
    assert vals["company_type"] == "company"
    assert vals["justech_do_partner_id_type"] == "1"
    assert vals["justech_do_fiscal_config_state"] == "confirmed_history"
    assert vals["justech_do_default_document_type_id"] == 9


def test_resolve_pdf_path_skips_directory_and_empty_source(tmp_path):
    named = tmp_path / "DORALEX_B1500000147.pdf"
    named.write_bytes(b"%PDF-1.4 fake")
    (tmp_path / "pdfs").mkdir()
    assert resolve_pdf_path(tmp_path, "DORALEX", "B1500000147", None, None) == named
    assert resolve_pdf_path(tmp_path, "DORALEX", "B1300000016", "", None) is None
    assert resolve_pdf_path(tmp_path, "DORALEX", "B1300000016", None, None) is None
    # a directory named like the source must never be opened as the PDF
    assert resolve_pdf_path(tmp_path, "MAYUMA", "B1500000109", "pdfs", 1) is None


def test_opening_clearing_account_uses_chart_not_bank():
    assert is_opening_clearing_account("11030205", "Other Accounts Receivable")
    assert is_opening_clearing_account("11030205", "Otras cuentas por cobrar")
    assert not is_opening_clearing_account("11010100", "Banco Banreservas")
    assert not is_opening_clearing_account("101401", "Outstanding Receipts")
    assert not is_opening_clearing_account("11010101", "Caja general")
