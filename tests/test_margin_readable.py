"""Invoice form must not AccessError on unreadable margin transactions."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BASE = REPO / "addons" / "alexander" / "justech_alexander_base"


def test_margin_readable_overlay_exists() -> None:
    manifest = (BASE / "__manifest__.py").read_text(encoding="utf-8")
    src = (BASE / "models" / "margin_readable.py").read_text(encoding="utf-8")
    init = (BASE / "models" / "__init__.py").read_text(encoding="utf-8")
    assert "19.0.1.0.22" in manifest
    assert "margin_readable" in init
    assert "_dx_keep_readable_mtx" in src
    assert "_dx_web_read_without_forbidden_mtx" in src
    assert "purchase.sale.margin.transaction" in src
    assert "group_ids" not in src
    assert "implied_ids" not in src
    assert "ir.model.access" not in src
    assert "action_post" not in src
    assert "consume" not in src.lower()
    assert "_compute_margin_transaction_ids" not in src
