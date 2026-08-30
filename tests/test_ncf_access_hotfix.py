"""Hotfix Odoo 19: wizards NCF deben aceptar _check_access(operation)."""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
NCF = (
    REPO / "addons/vendor/odoo-custom-addons/custom/justech/justech_l10n_do_ncf/wizards"
)


def _fn_args(path: Path, name: str) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == name:
                    return [a.arg for a in item.args.args]
    raise AssertionError(f"{name} no encontrado en {path}")


def test_migration_wizard_check_access_has_operation() -> None:
    args = _fn_args(NCF / "ncf_migration_wizard.py", "_check_access")
    assert args == ["self", "operation"]


def test_reconcile_wizard_check_access_has_operation() -> None:
    args = _fn_args(NCF / "ncf_reconcile_wizard.py", "_check_access")
    assert args == ["self", "operation"]


def test_wizards_call_check_access_not_bare() -> None:
    for name in ("ncf_migration_wizard.py", "ncf_reconcile_wizard.py"):
        text = (NCF / name).read_text(encoding="utf-8")
        assert "self.check_access(" in text
        assert "self._check_access()" not in text
        assert "sudo()" not in text
        assert "super()._check_access(operation)" in text
