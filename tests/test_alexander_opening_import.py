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
            "ncf": "B1500000999",
            "vat": "430128368",
            "amount_original": "249754.56",
            "balance_ok": True,
        }
    ]
    pdf = [
        {
            "company": "INVERSIONES DORALEX,S.RL.",
            "ncf": "B1500000999",
            "customer_vat": "430128368",
            "total": "294754.56",
        }
    ]
    result = match_invoices(cxc, pdf)
    assert result["blocked"][0]["EXCEL_PDF_MATCH"] == "FAIL"


def test_pdf_total_override_0150():
    cxc = [
        {
            "company": "INVERSIONES DORALEX,S.RL.",
            "ncf": "B1500000150",
            "vat": "430128368",
            "amount_original": "249754.56",
            "amount_paid": "0",
            "amount_residual": "249754.56",
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
    assert result["blocked"] == []
    rec = result["matched"][0]
    assert rec["TOTAL_OVERRIDE"] == "PDF"
    assert rec["amount_original"] == "294754.56"
    assert rec["amount_residual"] == "294754.56"
    assert rec["excel_amount_original"] == "249754.56"


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


def test_pdf_total_override_rempart_110_even_if_catalog_copied_excel():
    cxc = [
        {
            "company": "REMPART GROUP S.R.L.",
            "ncf": "B1500000110",
            "vat": "423002565",
            "amount_original": "267250.53",
            "amount_paid": "0",
            "amount_residual": "267250.53",
            "balance_ok": True,
        }
    ]
    pdf = [
        {
            "company": "REMPART GROUP S.R.L.",
            "ncf": "B1500000110",
            "customer_vat": "423002565",
            "total": "267250.53",
        }
    ]
    result = match_invoices(cxc, pdf)
    rec = result["matched"][0]
    assert rec["amount_original"] == "267250.52"
    assert rec["amount_residual"] == "267250.52"


def test_pdf_total_override_rempart_110():
    cxc = [
        {
            "company": "REMPART GROUP S.R.L.",
            "ncf": "B1500000110",
            "vat": "430128368",
            "amount_original": "267250.53",
            "amount_paid": "0",
            "amount_residual": "267250.53",
            "balance_ok": True,
        }
    ]
    pdf = [
        {
            "company": "REMPART GROUP S.R.L.",
            "ncf": "B1500000110",
            "customer_vat": "430128368",
            "total": "267250.52",
        }
    ]
    result = match_invoices(cxc, pdf)
    assert result["blocked"] == []
    rec = result["matched"][0]
    assert rec["amount_original"] == "267250.52"
    assert rec["amount_residual"] == "267250.52"
    assert rec["override_reason"] == (
        "PDF_SOURCE_DOCUMENT_OVERRIDES_EXCEL_TRANSCRIPTION_ERROR"
    )


def test_missing_pdf_is_not_blocked():
    result = match_invoices(
        [
            {
                "company": "INVERSIONES DORALEX,S.RL.",
                "ncf": "B1300000016",
                "vat": "401007363",
                "amount_original": "100.00",
                "amount_residual": "100.00",
                "balance_ok": True,
            }
        ],
        [],
    )
    assert result["matched"] == []
    assert result["blocked"] == []
    assert result["missing_pdf"][0]["SOURCE_DOCUMENT_STATUS"] == "MISSING_PDF"


def test_ncf_reconstruct_next_is_max_plus_one_inside_range():
    from tools.alexander_opening_import.ncf_reconstruct import reconstruct_row

    rec = reconstruct_row(
        {
            "company": "INVERSIONES DORALEX,S.RL.",
            "declared_type": "B15",
            "range_from": "B1500000141",
            "range_to": "B1500000160",
            "last_used": "B1500000151",
            "next": "B1500000151",
            "authorization": "A1",
            "expiration": "2026-12-31",
        },
        ["B1500000147", "B1500000151", "B1500000150"],
    )
    assert rec["max_historical_ncf_found"] == "B1500000151"
    assert rec["calculated_next"] == "B1500000152"
    assert rec["status"] == "SAFE_TO_ACTIVATE"
    assert rec["activate"] is True


def test_ncf_reconstruct_blocks_when_max_outside_range():
    from tools.alexander_opening_import.ncf_reconstruct import reconstruct_row

    rec = reconstruct_row(
        {
            "company": "INVERSIONES DORALEX,S.RL.",
            "declared_type": "B13",
            "range_from": "B1300000011",
            "range_to": "B1300000015",
            "last_used": "B1300000015",
            "next": "B1300000016",
            "authorization": "A1",
            "expiration": "2026-12-31",
        },
        ["B1300000016"],
    )
    assert rec["max_historical_ncf_found"] == "B1300000016"
    assert rec["calculated_next"] == "B1300000017"
    assert rec["activate"] is False
    assert rec["needs_fiscal_range_confirmation"] is True
    assert rec["status"] == "MAX_OUTSIDE_DECLARED_RANGE"


def test_ncf_reconstruct_ignores_planilla_and_qa_prefixes():
    from tools.alexander_opening_import.ncf_reconstruct import reconstruct_row

    rec = reconstruct_row(
        {
            "company": "INVERSIONES DORALEX,S.RL.",
            "declared_type": "B01",
            "range_from": "B0100000052",
            "range_to": "B0100000087",
            "last_used": "B1500000151",
            "next": "B1500000152",
            "authorization": "A1",
            "expiration": "2026-12-31",
        },
        ["B0100000053", "B0199100100"],
    )
    assert rec["max_historical_ncf_found"] == "B0100000053"
    assert rec["calculated_next"] == "B0100000054"
    assert rec["activate"] is True
    assert "PLANILLA_LAST_PREFIX_IGNORED" in rec["notes"]
    assert "PLANILLA_NEXT_PREFIX_IGNORED" in rec["notes"]


def test_ncf_reconstruct_no_historical_does_not_use_planilla_next():
    from tools.alexander_opening_import.ncf_reconstruct import reconstruct_row

    rec = reconstruct_row(
        {
            "company": "BLUE ELITE, S.R.L.",
            "declared_type": "B15",
            "range_from": "B1500000001",
            "range_to": "B1500000020",
            "last_used": "B1500000101",
            "next": "B1500000102",
            "authorization": "A1",
            "expiration": "2026-12-31",
        },
        [],
    )
    assert rec["activate"] is False
    assert rec["calculated_next"] is None
    assert rec["status"] == "NO_HISTORICAL_NCF"


def test_opening_clearing_account_uses_chart_not_bank():
    assert is_opening_clearing_account("11030205", "Other Accounts Receivable")
    assert is_opening_clearing_account("11030205", "Otras cuentas por cobrar")
    assert not is_opening_clearing_account("11010100", "Banco Banreservas")
    assert not is_opening_clearing_account("101401", "Outstanding Receipts")
    assert not is_opening_clearing_account("11010101", "Caja general")
