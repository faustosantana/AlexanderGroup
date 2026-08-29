"""Detección del árbol Enterprise 19 desde un archive extraído."""

from __future__ import annotations

from pathlib import Path

from tools.enterprise_source import find_enterprise_addons_root, manifest_version


def _write_module(root: Path, name: str) -> None:
    d = root / name
    d.mkdir(parents=True)
    (d / "__manifest__.py").write_text(
        f'{{"name": "{name}", "version": "19.0.1.0.0"}}\n', encoding="utf-8"
    )


def test_finds_enterprise_root(tmp_path: Path) -> None:
    bundle = tmp_path / "odoo-19.0+e.20260829"
    addons = bundle / "enterprise"
    _write_module(addons, "web_enterprise")
    _write_module(addons, "account_accountant")
    found = find_enterprise_addons_root(bundle)
    assert found == addons
    assert "19.0" in manifest_version(found / "web_enterprise")


def test_rejects_community_only(tmp_path: Path) -> None:
    _write_module(tmp_path / "community", "web")
    try:
        find_enterprise_addons_root(tmp_path)
    except FileNotFoundError:
        return
    raise AssertionError("debió fallar sin web_enterprise")
