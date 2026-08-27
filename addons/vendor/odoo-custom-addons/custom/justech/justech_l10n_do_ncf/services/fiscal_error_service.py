# -*- coding: utf-8 -*-
"""Traducción centralizada de errores fiscales / NCF a mensajes de usuario.

HOTFIX 2026.1.1 — nunca exponer IntegrityError / mensajes PostgreSQL al usuario.
"""
from __future__ import annotations

import re

from odoo import _, models
from odoo.exceptions import UserError, ValidationError

try:
    from psycopg2 import Error as PsycopgError
except ImportError:  # pragma: no cover
    PsycopgError = Exception

_NCF_RE = re.compile(r"\b([BE]\d{2}\d{7,})\b", re.IGNORECASE)

# Unique indexes created by justech_l10n_do_ncf on account_move
_SALE_UNIQ = "account_move_justech_do_ncf_sale_uniq"
_PURCHASE_UNIQ = "account_move_justech_do_ncf_purchase_uniq"
_LEGACY_UNIQ = "account_move_justech_do_ncf_company_uniq"


class JustechDoFiscalErrorService(models.AbstractModel):
    _name = "justech.do.fiscal.error.service"
    _description = "Justech Fiscal User-Facing Error Mapper"

    def reraise_as_user_error(self, exc, move=None, company=None, ncf=None):
        """Raise UserError with a functional message, or re-raise if not fiscal."""
        mapped = self.map_exception(exc, move=move, company=company, ncf=ncf)
        if mapped is None:
            raise exc
        raise UserError(mapped) from exc

    def map_exception(self, exc, move=None, company=None, ncf=None):
        """Return translated message string, or None if not a known fiscal error."""
        if isinstance(exc, (UserError, ValidationError)):
            return None  # already user-facing
        text = self._exception_text(exc)
        if not text:
            return None
        lower = text.lower()
        company_name = self._company_name(move, company)
        ncf_val = ncf or self._extract_ncf(text, move)

        if _SALE_UNIQ in text or (
            "duplicate key" in lower and "justech_do_ncf_sale" in lower
        ):
            return self.message_duplicate_sale(ncf_val, company_name)
        if _PURCHASE_UNIQ in text or (
            "duplicate key" in lower and "justech_do_ncf_purchase" in lower
        ):
            return self.message_duplicate_purchase(ncf_val, company_name, move)
        if _LEGACY_UNIQ in text or (
            "duplicate key" in lower
            and "justech_do_ncf" in lower
            and "uniq" in lower
        ):
            return self.message_duplicate_generic(ncf_val, company_name)
        if "duplicate key" in lower and "ncf" in lower:
            return self.message_duplicate_generic(ncf_val, company_name)
        return None

    def message_duplicate_sale(self, ncf, company_name):
        if ncf:
            return _(
                "No fue posible emitir el comprobante fiscal.\n\n"
                "El NCF %(ncf)s ya fue utilizado en otra factura de %(company)s.\n\n"
                "Cada NCF debe ser único según la normativa DGII.\n"
                "Revise la configuración del rango fiscal o contacte al administrador.",
                ncf=ncf,
                company=company_name or _("la empresa"),
            )
        return _(
            "El comprobante fiscal ya existe.\n\n"
            "Cada NCF debe ser único según la normativa DGII.\n"
            "Verifique el rango de comprobantes antes de continuar."
        )

    def message_duplicate_purchase(self, ncf, company_name, move=None):
        partner = ""
        if move and move.partner_id:
            partner = move.partner_id.display_name
        if ncf and partner:
            return _(
                "No fue posible registrar el comprobante fiscal.\n\n"
                "El NCF %(ncf)s del proveedor %(partner)s ya está registrado "
                "en %(company)s.\n\n"
                "Verifique el NCF del proveedor antes de continuar.",
                ncf=ncf,
                partner=partner,
                company=company_name or _("la empresa"),
            )
        return self.message_duplicate_generic(ncf, company_name)

    def message_duplicate_generic(self, ncf, company_name):
        if ncf:
            return _(
                "El comprobante fiscal ya existe.\n\n"
                "El NCF %(ncf)s ya fue utilizado%(company)s.\n"
                "Cada NCF debe ser único según la normativa DGII.\n"
                "Verifique el rango de comprobantes antes de continuar.",
                ncf=ncf,
                company=(
                    _(" en %(company)s") % {"company": company_name}
                    if company_name
                    else ""
                ),
            )
        return _(
            "El comprobante fiscal ya existe.\n\n"
            "Cada NCF debe ser único según la normativa DGII.\n"
            "Verifique el rango de comprobantes antes de continuar."
        )

    def message_no_range(self, company_name=None):
        if company_name:
            return _(
                "No existe un NCF disponible para %(company)s.\n\n"
                "Revise el rango fiscal configurado.",
                company=company_name,
            )
        return _(
            "No existe un NCF disponible para esta empresa.\n\n"
            "Revise el rango fiscal configurado."
        )

    def message_range_depleted(self, prefix=None, company_name=None):
        return _(
            "El rango fiscal configurado está agotado%(detail)s.",
            detail=self._detail_prefix_company(prefix, company_name),
        )

    def message_range_expired(self, prefix=None, company_name=None):
        return _(
            "El rango fiscal configurado está vencido%(detail)s.",
            detail=self._detail_prefix_company(prefix, company_name),
        )

    def message_type_range_mismatch(self):
        return _(
            "El tipo de comprobante seleccionado no pertenece al rango fiscal activo."
        )

    def _detail_prefix_company(self, prefix, company_name):
        parts = []
        if prefix:
            parts.append(prefix)
        if company_name:
            parts.append(company_name)
        if not parts:
            return ""
        return _(" (%(info)s)") % {"info": " — ".join(parts)}

    def _company_name(self, move, company):
        if move and move.company_id:
            return move.company_id.display_name
        if company:
            return company.display_name
        return ""

    def _extract_ncf(self, text, move=None):
        if move:
            for attr in ("justech_do_ncf", "l10n_latam_document_number"):
                val = getattr(move, attr, None) or ""
                if val:
                    return val
        match = _NCF_RE.search(text or "")
        return match.group(1).upper() if match else ""

    def _exception_text(self, exc):
        parts = [str(exc or "")]
        if isinstance(exc, PsycopgError):
            parts.append(getattr(exc, "pgerror", "") or "")
            parts.append(getattr(exc, "diag", None) and getattr(exc.diag, "message_primary", "") or "")
        cause = getattr(exc, "__cause__", None) or getattr(exc, "orig", None)
        if cause is not None and cause is not exc:
            parts.append(self._exception_text(cause))
        return "\n".join(p for p in parts if p)
