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


def test_manifest_versions_bumped():
    base = (BASE / "__manifest__.py").read_text(encoding="utf-8")
    ux = (UX / "__manifest__.py").read_text(encoding="utf-8")
    assert "19.0.1.0.7" in base
    assert "justech_accounting_recovery" in base
    assert "res_partner_views.xml" in base
    assert "19.0.1.6.0" in ux
    assert "withholding_catalog_views.xml" in ux
