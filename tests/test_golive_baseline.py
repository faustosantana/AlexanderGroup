"""Go-live baseline evidence and product-nature closeout."""

from __future__ import annotations

import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EV = (
    REPO
    / "docs"
    / "enterprise_conversion"
    / "evidence"
    / "ALEXANDER_GROUP_GO_LIVE_BASELINE_20260926"
)

REQUIRED = (
    "01_system_info.md",
    "02_companies.md",
    "03_users_permissions.md",
    "04_products.md",
    "05_product_types.md",
    "06_accounting.md",
    "07_taxes.md",
    "08_ncf.md",
    "09_sales.md",
    "10_purchase.md",
    "11_invoicing.md",
    "12_inventory.md",
    "13_approvals.md",
    "14_reports.md",
    "15_security.md",
    "16_backups_restore.md",
    "17_tests.md",
    "18_known_pending.md",
    "19_final_scorecard.md",
    "19_final_scorecard.json",
    "PRODUCT_TYPE_FINAL_AUDIT.csv",
)


def test_baseline_evidence_files_exist():
    assert EV.is_dir()
    for name in REQUIRED:
        assert (EV / name).is_file(), name


def test_scorecard_ready_with_non_blocking_and_no_critical():
    data = json.loads((EV / "19_final_scorecard.json").read_text(encoding="utf-8"))
    assert data["COMPANIES_AUDITED"] == 6
    assert data["CROSS_COMPANY_TAX_REFERENCE"] == 0
    assert data["PROD_AR_DIFFERENCE"] == 0.0
    assert data["UNBALANCED_MOVES"] == 0
    assert data["CRITICAL_ERRORS"] == 0
    assert data["HIGH_ERRORS"] == 0
    assert data["SECURITY_CRITICAL_FINDINGS"] == 0
    assert data["MAIL_SENT"] == 0
    assert data["DGII_SENT"] == 0
    assert data["ECF_SENT"] == 0
    assert data["RESTORE_TEST"] == "PASS"
    assert data["BACKUP_VALIDATED"] == "PASS"
    assert data["PRODUCT_TYPE_WRITES_THIS_CLOSEOUT"] == 0
    assert data["HISTORICAL_DOCUMENTS_CHANGED"] == 0
    assert data["STOCK_INVENTED"] == 0
    assert data["FINAL_GO_LIVE_BASELINE_STATUS"] == "READY_WITH_NON_BLOCKING_PENDING"
    assert data["NEGATIVE_PERMISSION_QA"] == "PASS"
    assert data["GEILIN_ACCOUNTING_ADMIN"] == "NO"
    assert data["GRAVA_TYPE"] == "consu"
    assert data["SERVICIOS_168_TYPE"] == "service"
    assert data["PRODUCT_138_ARCHIVED"] is True


def test_explain_1601_vs_1736_is_scope_not_rewrite():
    text = (EV / "04_products.md").read_text(encoding="utf-8")
    assert "EXPLAIN_1601_VS_1736" in text
    assert "1601" in text and "1736" in text
    assert "Do not change data" in text


def test_product_type_audit_csv_keeps_canonical_and_archived():
    rows = list(
        csv.DictReader((EV / "PRODUCT_TYPE_FINAL_AUDIT.csv").open(encoding="utf-8"))
    )
    assert len(rows) == 1750
    by_id = {int(r["PRODUCT_ID"]): r for r in rows}
    grava = by_id[21]
    assert grava["CURRENT_TYPE"] == "consu"
    assert grava["ACTION"] == "KEEP"
    archived = by_id[138]
    assert archived["ACTION"] == "KEEP_ARCHIVED"
    svc = by_id[168]
    assert svc["CURRENT_TYPE"] == "service"
    assert svc["ACTION"] == "KEEP"
    assert svc["PROPOSED_TYPE"] == "service"


def test_odoo19_goods_are_consu_not_legacy_product():
    text = (EV / "05_product_types.md").read_text(encoding="utf-8")
    assert "type='consu'" in text
    assert "is_storable" in text
    assert "type='service'" in text


def test_restore_and_ncf_decisions_documented():
    backup = (EV / "16_backups_restore.md").read_text(encoding="utf-8")
    ncf = (EV / "08_ncf.md").read_text(encoding="utf-8")
    assert "pre_fix_multicompany_tax_access_20260926_133358" in backup
    assert "RESTORE_TEST = PASS" in backup
    assert "doralex_restore_golive_20260926" in backup
    assert "Doralex B15" in ncf
    assert "B13" in ncf
    assert "No ranges activated" in ncf or "no ranges activated" in ncf.lower()
