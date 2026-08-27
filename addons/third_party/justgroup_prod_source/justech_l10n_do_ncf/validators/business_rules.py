"""Reglas de negocio fiscal NCF — validadores puros (spec Adel, arquitectura Justech)."""
from __future__ import annotations

SPECIAL_EXEMPT_PREFIXES = frozenset({"B14"})
EXPORT_PREFIXES = frozenset({"B16"})
CONSUMER_DOC_PREFIXES = frozenset({"B02", "B12"})
HIGH_AMOUNT_RNC_THRESHOLD = 250_000.0


def validate_b14_no_itbis(*, prefix: str, line_taxes: list[dict]) -> str | None:
    """B14 régimen especial: líneas no deben llevar ITBIS/ISC positivo."""
    if prefix not in SPECIAL_EXEMPT_PREFIXES:
        return None
    for tax in line_taxes:
        if tax.get("type_tax_use") == "sale" and (tax.get("amount") or 0) > 0:
            return (
                "El comprobante B14 (régimen especial) no puede incluir líneas con ITBIS o ISC."
            )
    return None


def validate_high_amount_requires_rnc(
    *,
    prefix: str,
    move_type: str,
    amount_total: float,
    partner_has_rnc: bool,
) -> str | None:
    """Facturas de consumo ≥ RD$250,000 exigen RNC del cliente (Norma DGII)."""
    if move_type != "out_invoice" or prefix not in CONSUMER_DOC_PREFIXES:
        return None
    if amount_total >= HIGH_AMOUNT_RNC_THRESHOLD and not partner_has_rnc:
        return (
            "Las facturas de consumo iguales o superiores a RD$250,000.00 "
            "requieren RNC válido del cliente."
        )
    return None


def validate_export_invoice(
    *,
    prefix: str,
    move_type: str,
    partner_country_code: str | None,
    line_products: list[dict],
) -> str | None:
    """B16 exportaciones: cliente extranjero; bienes vs servicios coherentes."""
    if prefix not in EXPORT_PREFIXES or move_type != "out_invoice":
        return None
    if not partner_country_code or partner_country_code == "DO":
        return (
            "El comprobante B16 (exportaciones) requiere un cliente con país distinto "
            "a República Dominicana."
        )
    if not line_products:
        return "El comprobante B16 requiere al menos una línea de producto o servicio."
    has_goods = any(p.get("is_storable") or p.get("type") == "consu" for p in line_products)
    has_services = any(p.get("type") == "service" for p in line_products)
    if has_goods and has_services:
        return (
            "El comprobante B16 no debe mezclar bienes exportables y servicios "
            "en el mismo documento (Norma 05-19)."
        )
    return None
