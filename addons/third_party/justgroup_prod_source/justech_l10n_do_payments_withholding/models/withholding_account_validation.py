# -*- coding: utf-8 -*-
"""Validación de cuentas contables para retenciones (fail-closed)."""
from __future__ import annotations

from odoo import _
from odoo.exceptions import ValidationError

# Tipos Odoo 19 que nunca pueden ser cuenta de retención.
FORBIDDEN_ACCOUNT_TYPES = frozenset(
    {
        "asset_cash",
        "asset_credit_card",
        "off_balance",
    }
)

# Etiquetas de UI (alto nivel). No afectan validación fail-closed.
NATURE_LABELS = {
    "asset_receivable": "Activo",
    "asset_cash": "Activo",
    "asset_current": "Activo",
    "asset_non_current": "Activo",
    "asset_prepayments": "Activo",
    "asset_fixed": "Activo",
    "liability_payable": "Pasivo",
    "liability_credit_card": "Pasivo",
    "liability_current": "Pasivo",
    "liability_non_current": "Pasivo",
    "equity": "Patrimonio",
    "equity_unaffected": "Patrimonio",
    "income": "Ingreso",
    "income_other": "Ingreso",
    "expense": "Gasto",
    "expense_depreciation": "Gasto",
    "expense_direct_cost": "Gasto",
    "off_balance": "Fuera de balance",
}


def account_nature_label(account):
    if not account:
        return ""
    return NATURE_LABELS.get(account.account_type, account.account_type or "")


def account_belongs_to_company(account, company):
    """True si la cuenta es usable en la compañía (Odoo 19 company_ids)."""
    if not account or not company:
        return False
    if "company_ids" in account._fields:
        return not account.company_ids or company in account.company_ids
    if "company_id" in account._fields:
        return not account.company_id or account.company_id == company
    return True


def is_bank_or_liquidity_account(account, company=None):
    """Detecta liquidez / diario bank-cash / outstanding de métodos de pago."""
    if not account:
        return True
    if account.account_type in FORBIDDEN_ACCOUNT_TYPES:
        return True
    Journal = account.env["account.journal"]
    domain = [
        ("type", "in", ("bank", "cash")),
        "|",
        ("default_account_id", "=", account.id),
        ("suspense_account_id", "=", account.id),
    ]
    if company:
        domain = [("company_id", "=", company.id)] + domain
    if Journal.search(domain, limit=1):
        return True
    MethodLine = account.env["account.payment.method.line"]
    ml_domain = [("payment_account_id", "=", account.id)]
    if company:
        ml_domain = [("journal_id.company_id", "=", company.id)] + ml_domain
    for ml in MethodLine.search(ml_domain):
        if ml.journal_id.type in ("bank", "cash"):
            return True
    return False


def assert_withholding_account_allowed(account, company, *, raise_exception=True):
    """
    Valida cuenta para retención. Fail-closed.
    Retorna (ok: bool, error_code: str|False, message: str).
    """
    if not account:
        msg = _("Debe indicar una cuenta contable de retención.")
        if raise_exception:
            raise ValidationError(msg)
        return False, "missing", msg

    if getattr(account, "deprecated", False) or (
        "active" in account._fields and not account.active
    ):
        msg = _("La cuenta contable seleccionada está archivada y no puede utilizarse.")
        if raise_exception:
            raise ValidationError(msg)
        return False, "archived", msg

    if not account_belongs_to_company(account, company):
        msg = _(
            "La cuenta contable seleccionada no pertenece a la empresa configurada."
        )
        if raise_exception:
            raise ValidationError(msg)
        return False, "wrong_company", msg

    # Cuentas de vista / consolidación (si el campo existe)
    if getattr(account, "internal_group", None) == "off" and account.account_type == "off_balance":
        msg = _("La cuenta contable no permite movimientos de retención.")
        if raise_exception:
            raise ValidationError(msg)
        return False, "off_balance", msg

    if is_bank_or_liquidity_account(account, company):
        msg = _(
            "No puede utilizar una cuenta bancaria, de caja o de liquidez como "
            "cuenta contable de una retención."
        )
        if raise_exception:
            raise ValidationError(msg)
        return False, "liquidity", msg

    return True, False, ""


def nature_compatibility_warning(catalog, account):
    """
    Advertencia (no bloqueo) si naturaleza parece incompatible.
    Bloqueo solo liquidez/empresa/archivada — ver ACCOUNT_NATURE_RULES.md.
    """
    if not catalog or not account:
        return ""
    nature = account.account_type or ""
    is_asset = nature.startswith("asset_")
    is_liability = nature.startswith("liability_")
    # Cobro / cliente → normalmente activo (nos retienen)
    expects_asset = catalog.partner_scope in ("customer",) or (
        catalog.move_scope == "sale" and catalog.partner_scope == "both"
    )
    # Pago / proveedor → normalmente pasivo (retenemos)
    expects_liability = catalog.partner_scope in ("supplier",) or (
        catalog.move_scope == "purchase" and catalog.partner_scope == "both"
    )
    if catalog.partner_scope == "both" and catalog.move_scope == "both":
        return ""
    if expects_asset and is_liability and not expects_liability:
        return _(
            "La cuenta seleccionada es de tipo Pasivo, pero esta retención está "
            "orientada a cobros (activo por cobrar). Revise la cuenta antes de activarla."
        )
    if expects_liability and is_asset and not expects_asset:
        return _(
            "La cuenta seleccionada es de tipo Activo, pero esta retención está "
            "configurada como obligación por pagar. Revise la cuenta antes de activarla."
        )
    if nature in ("income", "income_other", "expense", "expense_depreciation", "expense_direct_cost", "equity", "equity_unaffected"):
        return _(
            "La cuenta seleccionada es de naturaleza %(nature)s. "
            "Las retenciones suelen usar cuentas de activo o pasivo fiscal. Revise antes de activar.",
            nature=account_nature_label(account),
        )
    return ""
