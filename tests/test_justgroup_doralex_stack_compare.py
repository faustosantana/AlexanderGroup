"""Pruebas del comparador Justgroup vs Doralex (sin tocar servidores)."""

from __future__ import annotations

from pathlib import Path

from tools.justgroup_doralex_stack_compare import (
    build_report,
    edition_of,
    load_json,
    main,
    render_text,
)

REPO = Path(__file__).resolve().parent.parent
JG = REPO / "docs/stack_audit/justgroup_reference.json"
DX = REPO / "docs/stack_audit/doralex_live_inventory.json"


def test_edition_detects_enterprise_suffix() -> None:
    assert edition_of("19.0+e-20260324", [19, 0, 0, "final", 0, "e"]) == "enterprise"
    assert edition_of("19.0-20260817", [19, 0, 0, "final", 0, ""]) == "community"


def test_frozen_manifests_exist() -> None:
    assert JG.is_file()
    assert DX.is_file()
    dx = load_json(DX)
    assert dx["installed_count"] == 106
    assert dx["installed_count"] == len(dx["installed"])


def test_current_stack_is_rejected() -> None:
    report = build_report(load_json(JG), load_json(DX))
    flags = report["flags"]
    assert report["justgroup_odoo"] == "19.0+e-20260324"
    assert report["doralex_odoo"] == "19.0-20260817"
    assert report["justgroup_edition"] == "enterprise"
    assert report["doralex_edition"] == "community"
    assert flags["ODOO_VERSION_MATCH"] is False
    assert flags["ODOO_EDITION_MATCH"] is False
    assert flags["CUSTOM_MODULES_MATCH"] is False
    assert flags["SPANISH_UI"] is False
    assert flags["DORALEX_REPORTS_PRESERVED"] is True
    assert flags["JUSTGROUP_TRANSACTIONS_COPIED"] is False
    assert flags["JUSTGROUP_PRODUCTION_TOUCHED"] is False
    assert flags["CUTOVER_ALLOWED"] is False
    missing = {row["module"] for row in report["missing_custom"]}
    assert "justech_approval_flow" in missing
    assert "justech_purchase_sale_margin_control" in missing
    assert "justech_alexander_reports" in report["doralex_identity_extras"]
    text = render_text(report)
    assert "DORALEX_CLONE_STATUS = REJECTED" in text
    assert "SPANISH_UI = NO" in text


def test_cli_exits_rejected() -> None:
    assert main(["--justgroup", str(JG), "--doralex", str(DX)]) == 1
