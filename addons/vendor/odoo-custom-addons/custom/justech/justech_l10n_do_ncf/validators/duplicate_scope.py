"""Alcance de unicidad NCF v2.0 — ventas vs compras."""
from __future__ import annotations

SALE_MOVE_TYPES = frozenset({"out_invoice", "out_refund", "out_receipt"})
PURCHASE_MOVE_TYPES = frozenset({"in_invoice", "in_refund", "in_receipt"})


def fiscal_module_for_move_type(move_type: str | None) -> str:
    if move_type in SALE_MOVE_TYPES:
        return "ventas"
    if move_type in PURCHASE_MOVE_TYPES:
        return "compras"
    return "otro"


def move_types_for_module(module: str) -> tuple[str, ...]:
    if module == "ventas":
        return tuple(SALE_MOVE_TYPES)
    if module == "compras":
        return tuple(PURCHASE_MOVE_TYPES)
    return ()


def duplicate_search_domain(*, company_id: int, ncf: str, move_type: str, partner_id: int | False):
    """
    Dominio Odoo para detectar duplicado fiscal real (v2.0).
    Ventas: único por empresa + NCF en documentos de venta.
    Compras: único por empresa + NCF + proveedor (emisor).

    El NCF puede estar en ``justech_do_ncf`` (emisión Justech) o en
    ``l10n_latam_document_number`` (documento recibido del proveedor / histórico).
    """
    module = fiscal_module_for_move_type(move_type)
    domain = [
        ("company_id", "=", company_id),
        "|",
        ("justech_do_ncf", "=", ncf),
        ("l10n_latam_document_number", "=", ncf),
        ("state", "=", "posted"),
        ("justech_do_ncf_voided", "=", False),
        ("move_type", "in", list(move_types_for_module(module) or [move_type])),
    ]
    if module == "compras" and partner_id:
        domain.append(("partner_id", "=", partner_id))
    return domain
