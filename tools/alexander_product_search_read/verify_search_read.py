# ruff: noqa
"""Reproduce the OWL product.template/search_read that IndexError'd call_kw."""

from odoo.service.model import call_kw


def run(env):
    Product = env["product.template"]
    method = type(Product).search_read
    api_model = bool(getattr(method, "_api_model", False))
    print("SEARCH_READ_API_MODEL", api_model)
    kwargs = {
        "domain": [],
        "fields": ["id", "name", "taxes_id"],
        "limit": 3,
        "offset": 0,
    }
    try:
        rows = call_kw(Product, "search_read", [], kwargs)
    except Exception as exc:
        print("SEARCH_READ_EMPTY_ARGS", "FAIL", type(exc).__name__, str(exc)[:200])
        raise
    print("SEARCH_READ_EMPTY_ARGS", "PASS", len(rows))
    for row in rows:
        print(
            "ROW",
            row.get("id"),
            (row.get("name") or "")[:40],
            "taxes",
            row.get("taxes_id"),
        )
    print("SEARCH_READ_VERIFY_PASS")
    return True


run(env)
