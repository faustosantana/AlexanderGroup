"""Cierre STAGING: aprobaciones OFF, padrón OFF, borradores, retenciones 2026."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BASE = REPO / "addons" / "alexander" / "justech_alexander_base"
UX = REPO / "addons" / "alexander" / "justech_alexander_ux"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_withholding_math_itbis_30_is_on_tax_not_subtotal():
    math = _load(BASE / "models" / "withholding_math.py", "dx_wh_math")
    example = math.itbis_30_pj_example(100000, 18)
    assert example["itbis"] == math.money(18000)
    assert example["itbis_withheld"] == math.money(5400)
    assert example["neto"] == math.money(112600)
    assert example["total"] == math.money(118000)
    assert math.itbis_of_tax(18000, 30) != math.money(30000)


def test_withholding_math_itbis_100_and_professional_15():
    math = _load(BASE / "models" / "withholding_math.py", "dx_wh_math")
    example = math.professional_pf_example(100000, 18)
    assert example["isr_withheld"] == math.money(15000)
    assert example["itbis_withheld"] == math.money(18000)
    assert example["neto"] == math.money(85000)
    assert example["total"] == math.money(118000)


def test_withholding_math_technical_presumed_is_3_percent_effective():
    math = _load(BASE / "models" / "withholding_math.py", "dx_wh_math")
    detail = math.isr_technical_presumed(100000)
    assert detail["base_original"] == math.money(100000)
    assert detail["base_presunta"] == math.money(20000)
    assert detail["tasa"] == math.money(15)
    assert detail["retencion"] == math.money(3000)
    assert detail["efectiva_pct"] == math.money(3)
    example = math.technical_pf_example(100000, 18)
    assert example["isr_withheld"] == math.money(3000)
    assert example["itbis_withheld"] == math.money(18000)
    assert example["neto"] == math.money(97000)


def test_withholding_math_government_5_on_untaxed():
    math = _load(BASE / "models" / "withholding_math.py", "dx_wh_math")
    assert math.isr_on_untaxed(100000, 5) == math.money(5000)


def test_approval_hook_disables_company_flags():
    hooks = (UX / "hooks.py").read_text(encoding="utf-8")
    assert '"justech_approval_sale_enabled": False' in hooks
    assert '"justech_approval_purchase_enabled": False' in hooks
    assert '"justech_approval_invoice_enabled": False' in hooks
    assert '"justech_approval_sale_enabled": True' not in hooks
    assert "justech_approval_flow" not in hooks.split("VISIBLE_APPS")[1][:200]
    assert "apply_padron_disabled" in hooks
    assert "apply_withholding_catalog" in hooks
    assert "Aprobaciones (histórico)" in hooks


def test_padron_cron_forced_off_and_validate_button_hidden():
    hooks = (UX / "hooks.py").read_text(encoding="utf-8")
    partner = (BASE / "views" / "res_partner_views.xml").read_text(encoding="utf-8")
    rules = (BASE / "models" / "ncf_business_rules.py").read_text(encoding="utf-8")
    assert "ir_cron_justech_rnc_padron_auto_update" in hooks
    assert "action_justech_validate_rnc" in partner
    assert 'attribute name="invisible">1' in partner
    assert "pendiente de validar" in rules
    assert "return None" in rules


def test_draft_cancel_skips_recovery_only_for_drafts():
    source = (BASE / "models" / "account_move_draft.py").read_text(encoding="utf-8")
    assert "_dx_all_drafts" in source
    assert "justech_accounting_recovery.models.account_move" in source
    assert "button_cancel" in source
    assert "unlink" in source
    assert "button_draft" not in source
    assert 'state == "draft"' in source or "state == 'draft'" in source


def test_2026_catalog_codes_and_no_silent_legacy_overwrite():
    source = (UX / "models" / "withholding_catalog.py").read_text(encoding="utf-8")
    for code in (
        "DX-ISR-ESTADO-5",
        "DX-ISR-PROF-PF-15",
        "DX-ISR-TEC-PF-15",
        "DX-ISR-ALQ-PF-15",
        "DX-ITBIS-30-PJ",
        "DX-ITBIS-100-PF",
        "DX-ISR-DIV-10",
        "DX-ISR-EXT-REG-15",
        "DX-ISR-EXT-27",
    ):
        assert code in source
    assert "LEGACY_VS_2026" in source
    assert "No modificar el impuesto -10%" in source
    assert 'base_type": "itbis"' in source or '"base_type": "itbis"' in source
    assert "presumed_income_pct" in source
    assert "dx_sync_2026_catalog" in source
    assert "account_id" not in source or "account.id if account" in source


def test_no_hardcoded_ids_in_closeout_overlay():
    roots = (BASE, UX)
    for path in roots:
        for file in path.rglob("*"):
            if file.suffix not in {".py", ".xml"}:
                continue
            text = file.read_text(encoding="utf-8")
            assert "company_id=8" not in text
            assert "company_id = 8" not in text
            assert "tax_id=255" not in text
            assert "account_id=1" not in text
            assert "doralexgroup.cloud" not in text or file.name in {
                "approval_branding.xml",
                "__manifest__.py",
            }


def test_closeout_docs_exist():
    uat = (REPO / "docs" / "ALEXANDERGROUP_STAGING_UAT.md").read_text(encoding="utf-8")
    ready = (REPO / "docs" / "ALEXANDERGROUP_PRODUCTION_READINESS.md").read_text(
        encoding="utf-8"
    )
    wh = (REPO / "docs" / "ALEXANDERGROUP_RD_WITHHOLDINGS.md").read_text(
        encoding="utf-8"
    )
    assert "APPROVAL FLOW: DISABLED" in ready
    assert "DGII PADRON: DISABLED" in ready
    assert "READY FOR PROD: **YES**" in ready or "READY FOR PROD: YES" in ready
    assert "PROD TOUCHED: NO" in ready
    assert "DX-ISR-PROF-PF-15" in wh
    assert "Ley 30-26" in wh
    assert "ROLLBACK TESTED | YES" in uat or "ROLLBACK TESTED: YES" in ready


def test_production_prego_closes_blockers_without_go():
    prego = (REPO / "docs" / "ALEXANDERGROUP_PRODUCTION_PREGO.md").read_text(
        encoding="utf-8"
    )
    assert "READY FOR HUMAN GO: **NO**" in prego
    assert "ITBIS 16 SALE PROD: **MISSING**" in prego
    assert "SAFE TO LEAVE FROZEN" in prego
    assert "DXMAP_FAILS 0" in prego or "114/114" in prego
    assert "POST-DEPLOY FISCAL OPERABILITY" in prego
    assert "HOST=db" in prego
    assert "USER=doralex_prod" in prego
    assert "PROD TOUCHED: **NO**" in prego
    assert "docker stop doralex-production-odoo" in prego
    assert "pg_stat_activity" in prego


def test_production_preflight_doc_blocks_execution():
    pre = (REPO / "docs" / "ALEXANDERGROUP_PRODUCTION_PREFLIGHT.md").read_text(
        encoding="utf-8"
    )
    assert "PROD TOUCHED: NO" in pre
    assert "READY TO EXECUTE DEPLOYMENT: **NO**" in pre
    assert "doralex_prod" in pre
    assert "doralex-production-odoo" in pre
    assert "1599d132ce019a7d3c47e6c722acbc9139c80759" in pre
    assert (
        "-u justech_alexander_base,justech_alexander_ux,justech_alexander_reports"
        in pre
    )
    assert "Nunca `-u all`" in pre or "nunca `-u all`" in pre.lower()
    assert "MISSING ACCOUNT: **ninguna**" in pre or "MISSING ACCOUNT: 0" in pre
    assert "APPROVAL FLOW = OFF" in pre
    assert "PADRON" in pre and "OFF" in pre
    assert "pre_alexander_release_" in pre
    assert "CONFIRM=yes ALLOW_PROD=yes" in pre


def test_manifest_versions_bumped():
    base = (BASE / "__manifest__.py").read_text(encoding="utf-8")
    ux = (UX / "__manifest__.py").read_text(encoding="utf-8")
    reports = (
        REPO / "addons" / "alexander" / "justech_alexander_reports" / "__manifest__.py"
    ).read_text(encoding="utf-8")
    assert "19.0.1.0.9" in base
    assert "account_move_views.xml" in base
    assert "justech_accounting_recovery" in base
    assert "res_partner_views.xml" in base
    assert "19.0.1.6.4" in ux
    assert "account_move_views.xml" in ux
    assert "login_views.xml" in ux
    assert "show_login_form.js" in ux
    assert "withholding_catalog_views.xml" in ux
    assert "19.0.3.10.2" in reports
    assert "print_buttons.xml" in reports


def test_payment_receipt_shows_vendor_withholding_breakdown():
    compose = (
        REPO
        / "addons"
        / "alexander"
        / "justech_alexander_reports"
        / "models"
        / "report_compose.py"
    ).read_text(encoding="utf-8")
    xml = (
        REPO
        / "addons"
        / "alexander"
        / "justech_alexander_reports"
        / "reports"
        / "components.xml"
    ).read_text(encoding="utf-8")
    assert "liability_payable" in compose
    assert "ISR retenido" in compose
    assert "ITBIS retenido" in compose
    assert "Monto bruto" in xml
    assert "ISR retenido" in xml
    assert "ITBIS retenido" in xml
    assert "Otras retenciones" in xml
    assert "Neto pagado" in xml
    assert "Total aplicado" in xml


def test_production_deploy_report_success():
    deploy = (REPO / "docs" / "ALEXANDERGROUP_PRODUCTION_DEPLOY.md").read_text(
        encoding="utf-8"
    )
    assert "FINAL STATUS: SUCCESS" in deploy
    assert "BACKUP VERIFIED: YES" in deploy
    assert "1599d132ce019a7d3c47e6c722acbc9139c80759" in deploy
    assert "19.0.1.0.7" in deploy
    assert "19.0.1.6.0" in deploy
    assert "19.0.3.9.1" in deploy
    assert "ITBIS 16 SALE: PASS" in deploy
    assert "APPROVAL FLOW: OFF" in deploy
    assert "ROLLBACK EXECUTED: NO" in deploy
    assert "PROD TOUCHED: YES" in deploy
    assert "doralex_prod" in deploy
    assert "doralex-production-odoo" in deploy


def test_ux_login_form_not_hidden():
    login = (UX / "views" / "login_views.xml").read_text(encoding="utf-8")
    js = (UX / "static" / "src" / "login" / "show_login_form.js").read_text(
        encoding="utf-8"
    )
    navbar = (UX / "static" / "src" / "navbar" / "navbar.xml").read_text(
        encoding="utf-8"
    )
    assert 'inherit_id="web.login"' in login
    assert "oe_login_form" in login
    assert "showLoginForm" in js
    assert "d-none" in js
    assert "o_menu_brand_icon" not in navbar
    assert "t-on-click" not in navbar
    assert "?." not in navbar
    assert "Inicio" in navbar
