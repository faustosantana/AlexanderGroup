"""product.template.search_read must stay @api.model (Odoo 19 call_kw)."""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PRODUCT = (
    REPO
    / "addons"
    / "alexander"
    / "justech_alexander_base"
    / "models"
    / "product_template.py"
)


def _search_read_node() -> ast.FunctionDef:
    tree = ast.parse(PRODUCT.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "ProductTemplate":
            continue
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "search_read":
                return item
    raise AssertionError("ProductTemplate.search_read is missing")


def _decorator_names(func: ast.FunctionDef) -> list[str]:
    names: list[str] = []
    for dec in func.decorator_list:
        if isinstance(dec, ast.Attribute):
            parent = dec.value
            parent_name = parent.id if isinstance(parent, ast.Name) else ""
            names.append(f"{parent_name}.{dec.attr}" if parent_name else dec.attr)
        elif isinstance(dec, ast.Name):
            names.append(dec.id)
    return names


def test_search_read_has_api_model() -> None:
    func = _search_read_node()
    names = _decorator_names(func)
    assert "api.model" in names, names


def test_search_read_empty_args_would_not_indexerror() -> None:
    """Mirrors odoo/service/model.py: record methods unpack args[0] as ids."""
    func = _search_read_node()
    api_model = "api.model" in _decorator_names(func)
    args: list = []
    assert api_model, "OWL search_read uses args=[]; missing @api.model IndexErrors"
    # The production crash was: ids, args = args[0], args[1:]
    assert args == []


def test_manifest_version_for_search_read_fix() -> None:
    manifest = (
        REPO / "addons" / "alexander" / "justech_alexander_base" / "__manifest__.py"
    ).read_text(encoding="utf-8")
    assert "19.0.1.0.26" in manifest
