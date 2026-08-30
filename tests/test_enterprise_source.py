"""Detección del árbol Enterprise 19 desde archive extraído o .deb oficial."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.enterprise_source import (
    find_enterprise_addons_root,
    find_official_enterprise_deb,
    is_official_enterprise_package_name,
    manifest_version,
)


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


def test_finds_debian_deb_extract_layout(tmp_path: Path) -> None:
    addons = tmp_path / "usr/lib/python3/dist-packages/odoo/addons"
    _write_module(addons, "web_enterprise")
    _write_module(addons, "account_accountant")
    found = find_enterprise_addons_root(tmp_path)
    assert found == addons


def test_rejects_community_only(tmp_path: Path) -> None:
    _write_module(tmp_path / "community", "web")
    with pytest.raises(FileNotFoundError):
        find_enterprise_addons_root(tmp_path)


@pytest.mark.parametrize(
    ("name", "ok"),
    [
        ("odoo_19.0+e.20260829_all.deb", True),
        ("odoo_19.0+e.latest_all.deb", True),
        ("odoo_19.0e.20260829_all.deb", True),
        ("odoo-enterprise-19.0.deb", True),
        ("odoo_19.0.20260817_all.deb", False),
        ("odoo_19.0.latest_all.deb", False),
        ("odoo_19.0+e.20260829.tar.gz", True),
        ("odoo_19.0.20260817.tar.gz", False),
    ],
)
def test_official_package_name(name: str, ok: bool) -> None:
    assert is_official_enterprise_package_name(name) is ok


def test_find_official_deb_picks_enterprise(tmp_path: Path) -> None:
    (tmp_path / "odoo_19.0.20260817_all.deb").write_bytes(b"community")
    wanted = tmp_path / "odoo_19.0+e.20260829_all.deb"
    wanted.write_bytes(b"enterprise")
    assert find_official_enterprise_deb(tmp_path) == wanted


def test_find_official_deb_rejects_community_only(tmp_path: Path) -> None:
    (tmp_path / "odoo_19.0.latest_all.deb").write_bytes(b"community")
    with pytest.raises(FileNotFoundError):
        find_official_enterprise_deb(tmp_path)
