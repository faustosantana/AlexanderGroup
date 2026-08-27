"""Install hooks for Justech Global Audit Log."""

import logging

from psycopg2 import IntegrityError

_logger = logging.getLogger(__name__)

DEFAULT_ACTIVE_RULES = (
    ("res.partner", "Contactos"),
    ("sale.order", "Pedidos de venta"),
    ("product.template", "Plantillas de producto"),
)

DEFAULT_INACTIVE_RULES = (
    ("account.move", "Facturas y asientos"),
    ("account.payment", "Pagos"),
    ("stock.picking", "Albaranes"),
    ("stock.move", "Movimientos de stock"),
    ("pos.order", "Pedidos POS"),
    ("pos.session", "Sesiones POS"),
)


def post_init_hook(env):
    _register_justech_module(env)
    _ensure_default_policy(env)
    _ensure_default_rules(env)
    _grant_audit_access_to_admins(env)
    _backfill_forensic_logs(env)
    _load_sale_audit_actions(env)


def _backfill_forensic_logs(env):
    Log = env["justech.audit.log"].sudo()
    total = 0
    while True:
        count = Log._backfill_forensic_fields(batch_size=500)
        total += count
        if count < 500:
            break
    if total:
        _logger.info("Auditoría: backfill forense en %s registros", total)


def _load_sale_audit_actions(env):
    sale = env["ir.module.module"].search([("name", "=", "sale"), ("state", "=", "installed")], limit=1)
    if not sale:
        return
    try:
        from odoo.tools.convert import convert_file

        convert_file(
            env,
            "justech_global_audit_log",
            "data/sale_audit_actions.xml",
            idref={},
            mode="init",
            noupdate=True,
        )
    except Exception:
        _logger.exception("No se pudieron cargar acciones de auditoría para sale.order")


def _grant_audit_access_to_admins(env):
    """Ensure Settings / ERP managers can see the Auditoría app launcher."""
    audit_manager = env.ref(
        "justech_global_audit_log.group_justech_audit_manager", raise_if_not_found=False
    )
    if not audit_manager:
        return
    for xmlid in ("base.group_system", "base.group_erp_manager"):
        group = env.ref(xmlid, raise_if_not_found=False)
        if group and audit_manager not in group.implied_ids:
            group.sudo().write({"implied_ids": [(4, audit_manager.id)]})
    admin_users = env.ref("base.group_system").user_ids
    erp_manager = env.ref("base.group_erp_manager", raise_if_not_found=False)
    if erp_manager:
        admin_users |= erp_manager.user_ids
    for user in admin_users:
        if audit_manager not in user.group_ids:
            user.sudo().write({"group_ids": [(4, audit_manager.id)]})


def _ensure_default_policy(env):
    Policy = env["justech.audit.policy"].sudo().with_context(active_test=False)
    if Policy.search([], limit=1):
        return
    Policy.create(
        {
            "name": "Política global de auditoría",
            "active": True,
            "audit_create": True,
            "audit_write": True,
            "audit_unlink": True,
            "audit_events": False,
            "notes": (
                "Auditoría activa para modelos seguros. "
                "Modelos pesados (facturas, pagos, inventario, POS) "
                "permanecen desactivados hasta aprobación explícita."
            ),
        }
    )


def _register_justech_module(env):
    try:
        from odoo.addons.justech_modules.hooks_register import register_from_manifest_hook

        register_from_manifest_hook(env, "justech_global_audit_log")
    except ImportError:
        pass


def _ensure_default_rules(env):
    Rule = env["justech.audit.rule"].sudo().with_context(active_test=False)
    for model_name, label in DEFAULT_ACTIVE_RULES:
        _create_or_update_rule(Rule, env, model_name, label, active=True)
    for model_name, label in DEFAULT_INACTIVE_RULES:
        _create_or_update_rule(Rule, env, model_name, label, active=False)


def _create_or_update_rule(Rule, env, model_name, label, active):
    if model_name not in env:
        return
    model = env["ir.model"].search([("model", "=", model_name)], limit=1)
    if not model:
        return
    rule = Rule.search([("model_id", "=", model.id)], limit=1)
    if rule:
        if rule.active != active or rule.name != label:
            rule.write({"active": active, "name": label})
        return
    try:
        with env.cr.savepoint():
            Rule.create(
                {
                    "name": label,
                    "model_id": model.id,
                    "active": active,
                }
            )
    except IntegrityError:
        _logger.debug("Audit rule for %s already exists", model_name)
