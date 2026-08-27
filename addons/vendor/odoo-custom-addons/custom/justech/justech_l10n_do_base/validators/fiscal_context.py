"""Contexto fiscal puro — claves de unicidad y clasificación de módulo."""
from __future__ import annotations

SALE_MOVE_TYPES = frozenset({"out_invoice", "out_refund", "out_receipt"})
PURCHASE_MOVE_TYPES = frozenset({"in_invoice", "in_refund", "in_receipt"})


def fiscal_module_for_move_type(move_type: str | None) -> str:
    if move_type in SALE_MOVE_TYPES:
        return "ventas"
    if move_type in PURCHASE_MOVE_TYPES:
        return "compras"
    return "otro"


def ncf_prefix_from_ncf(ncf: str | None) -> str:
    normalized = (ncf or "").strip().upper()
    return normalized[:3] if len(normalized) >= 3 else ""


def fiscal_duplicate_key_v2(
    *,
    company_id: int,
    move_type: str,
    ncf: str,
    company_vat: str,
    partner_vat: str,
) -> tuple:
    """
    Clave fiscal v2.0 para detección de duplicados reales.
    Ventas: emisor = RNC empresa. Compras: emisor = RNC proveedor.
    """
    module = fiscal_module_for_move_type(move_type)
    prefix = ncf_prefix_from_ncf(ncf)
    ncf_upper = (ncf or "").strip().upper()
    if module == "compras":
        issuer = (partner_vat or "").strip().upper()
    else:
        issuer = (company_vat or str(company_id)).strip().upper()
    return (company_id, module, prefix, ncf_upper, issuer)
