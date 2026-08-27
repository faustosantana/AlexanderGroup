"""Post-init: catálogo retenciones DO y retiro menús/acciones pagos legacy."""
from __future__ import annotations


def _disable_legacy_payment_menus(env):
    """Desactiva menús/acciones del pago múltiple anterior sin desinstalar el módulo."""
    Menu = env["ir.ui.menu"].sudo()
    Action = env["ir.actions.act_window"].sudo()
    legacy_model = "multi.invoice.manual.payment.wizard"

    for menu in Menu.search([("name", "in", ("Pago de Múltiples Facturas", "Pagos múltiples"))]):
        menu.active = False

    # Raíces Contabilidad: community (vacío bajo Enterprise) y accountant
    for xmlid in ("account.menu_finance", "accountant.menu_accounting"):
        finance = env.ref(xmlid, raise_if_not_found=False)
        if not finance:
            continue
        for menu in Menu.search([("parent_id", "=", finance.id), ("name", "=", "Pagos")]):
            action = menu.action
            if action and getattr(action, "res_model", None) == legacy_model:
                menu.active = False

    actions = Action.search([("res_model", "=", legacy_model)])
    for action in actions:
        Menu.search([("action", "=", f"{action.type},{action.id}")]).write({"active": False})
        # Quitar binding de formularios/listas para que no cree pagos nuevos desde UI
        vals = {"binding_model_id": False}
        if "binding_view_types" in action._fields:
            vals["binding_view_types"] = False
        action.write(vals)


def _ensure_single_accounting_app(env):
    """Pagos/Auditoría Fiscal bajo accountant.menu_accounting; no bajo menu_finance."""
    accounting = env.ref("accountant.menu_accounting", raise_if_not_found=False)
    if not accounting:
        return
    for xmlid in (
        "justech_l10n_do_treasury.menu_finance_payments_root",
        "justech_l10n_do_reports.menu_justech_do_audit_root",
    ):
        menu = env.ref(xmlid, raise_if_not_found=False)
        if menu and menu.parent_id != accounting:
            menu.parent_id = accounting


def post_init_hook(env):
    _disable_legacy_payment_menus(env)
    _ensure_single_accounting_app(env)

    Catalog = env.get("justech.do.withholding.catalog")
    if not Catalog:
        return
    # Una sola sincronización global (no copiar por cada empresa).
    do_company = env["res.company"].search([]).filtered(
        lambda c: c.country_id and c.country_id.code == "DO"
    )[:1]
    if do_company:
        Catalog.sync_catalog_from_taxes(do_company)
        Catalog.ensure_company_configs()

    # Puente SoD: Administrador Fiscal implica Administrador de Retenciones.
    fiscal_mgr = env.ref("justech_fiscal_admin.group_justech_fiscal_admin_manager", raise_if_not_found=False)
    wh_admin = env.ref(
        "justech_l10n_do_payments_withholding.group_justech_withholding_catalog_admin",
        raise_if_not_found=False,
    )
    if fiscal_mgr and wh_admin and wh_admin not in fiscal_mgr.implied_ids:
        fiscal_mgr.sudo().write({"implied_ids": [(4, wh_admin.id)]})

    account_mgr = env.ref("account.group_account_manager", raise_if_not_found=False)
    if account_mgr and wh_admin and wh_admin not in account_mgr.implied_ids:
        account_mgr.sudo().write({"implied_ids": [(4, wh_admin.id)]})
