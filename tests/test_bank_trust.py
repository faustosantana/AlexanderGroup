"""Estructura del auto-trust de cuentas bancarias de compañía."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BASE = REPO / "addons" / "alexander" / "justech_alexander_base"


def test_manifest_version_and_bank_trust_files() -> None:
    manifest = (BASE / "__manifest__.py").read_text(encoding="utf-8")
    assert "19.0.1.0.23" in manifest
    for rel in (
        "models/res_partner_bank.py",
        "models/account_move_bank_trust.py",
        "migrations/19.0.1.0.21/end-trust_company_banks.py",
    ):
        assert (BASE / rel).is_file(), rel


def test_trusts_only_company_owned_banks() -> None:
    bank = (BASE / "models" / "res_partner_bank.py").read_text(encoding="utf-8")
    move = (BASE / "models" / "account_move_bank_trust.py").read_text(encoding="utf-8")
    hook = (BASE / "hooks.py").read_text(encoding="utf-8")
    init = (BASE / "models" / "__init__.py").read_text(encoding="utf-8")
    assert "_dx_is_company_owned_bank" in bank
    assert "_dx_is_company_partner" in bank
    assert "allow_out_payment" in bank
    assert "install_mode" in bank
    assert "group_ids" not in bank
    assert "implied_ids" not in bank
    assert "consume_next" not in bank
    assert "action_post" not in bank
    assert "_dx_trust_inbound_company_banks" in move
    assert "is_inbound" in move
    assert "super()._post" in move
    assert "action_post" not in move
    assert "_dx_trust_company_owned_banks" in hook
    assert "res_partner_bank" in init
    assert "account_move_bank_trust" in init


def test_migration_does_not_post_or_consume_ncf() -> None:
    mig = (
        BASE / "migrations" / "19.0.1.0.21" / "end-trust_company_banks.py"
    ).read_text(encoding="utf-8")
    assert "_dx_trust_company_owned_banks" in mig
    assert "action_post" not in mig
    assert "consume" not in mig.lower()
    assert "group_validate_bank_account" not in mig
