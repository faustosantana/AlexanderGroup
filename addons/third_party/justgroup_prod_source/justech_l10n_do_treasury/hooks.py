"""Hooks tesorería — un solo icono Contabilidad (Enterprise accountant)."""
from __future__ import annotations


def _ensure_payments_under_accountant(env):
    accounting = env.ref("accountant.menu_accounting", raise_if_not_found=False)
    if not accounting:
        return
    pagos = env.ref("justech_l10n_do_treasury.menu_finance_payments_root", raise_if_not_found=False)
    if pagos and pagos.parent_id != accounting:
        pagos.parent_id = accounting
    audit = env.ref("justech_l10n_do_reports.menu_justech_do_audit_root", raise_if_not_found=False)
    if audit and audit.parent_id != accounting:
        audit.parent_id = accounting


def _hide_duplicate_bank_recon_menu(env):
    """Pagos→Conciliación bancaria duplica el widget estándar (acceso vía Tablero)."""
    bank = env.ref(
        "justech_l10n_do_treasury.menu_finance_bank_reconciliation",
        raise_if_not_found=False,
    )
    if bank and bank.active:
        bank.active = False


def _hide_empty_account_finance_root(env):
    """Enterprise usa accountant.menu_accounting; account.menu_finance queda vacío → 2º icono."""
    finance = env.ref("account.menu_finance", raise_if_not_found=False)
    accounting = env.ref("accountant.menu_accounting", raise_if_not_found=False)
    if not finance or not accounting:
        return
    # Solo ocultar si no tiene hijos activos (evita romper installs sin accountant).
    children = env["ir.ui.menu"].search(
        [("parent_id", "=", finance.id), ("active", "=", True)]
    )
    if not children and finance.active:
        finance.active = False


def _label_vendor_refunds_as_credit_notes(env):
    """Etiqueta funcional en Proveedores (el menú estándar suele ser noupdate)."""
    refund = env.ref("account.menu_action_move_in_refund_type", raise_if_not_found=False)
    if refund and refund.name != "Notas de crédito":
        refund.name = "Notas de crédito"


def post_init_hook(env):
    _ensure_payments_under_accountant(env)
    _hide_duplicate_bank_recon_menu(env)
    _hide_empty_account_finance_root(env)
    _label_vendor_refunds_as_credit_notes(env)
    # Reafirmar retiro de menús/acciones legacy de pagos múltiples
    try:
        from odoo.addons.justech_l10n_do_payments_withholding.hooks import (
            _disable_legacy_payment_menus,
        )

        _disable_legacy_payment_menus(env)
    except Exception:
        pass
    # Refrescar indicador bancario (outstanding ≠ solo asset_cash)
    Payment = env["account.payment"].sudo()
    pays = Payment.search([("state", "in", ("in_process", "paid"))])
    if pays:
        pays._compute_treasury_bank_state()
        pays.flush_recordset(["treasury_bank_state"])
