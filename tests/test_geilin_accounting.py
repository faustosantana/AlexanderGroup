"""Geilin gets Accounting Administrator only — not Settings."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BASE = REPO / "addons" / "alexander" / "justech_alexander_base"


def test_geilin_accounting_grant_is_scoped() -> None:
    manifest = (BASE / "__manifest__.py").read_text(encoding="utf-8")
    users = (BASE / "models" / "res_users.py").read_text(encoding="utf-8")
    hook = (BASE / "hooks.py").read_text(encoding="utf-8")
    mig = (
        BASE / "migrations" / "19.0.1.0.23" / "end-grant_geilin_accounting.py"
    ).read_text(encoding="utf-8")
    assert "19.0.1.0.23" in manifest
    assert "_dx_grant_geilin_full_accounting" in users
    assert "geilin.rosario@inversionesdoralex.com" in users
    assert "account.group_account_manager" in users
    assert "account.group_validate_bank_account" in users
    assert "base.group_system" not in users
    assert "base.group_erp_manager" not in users
    assert "_dx_grant_geilin_full_accounting" in hook
    assert "_dx_grant_geilin_full_accounting" in mig
    assert "base.group_system" not in mig
