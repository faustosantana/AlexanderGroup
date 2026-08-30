"""Catálogo y banderas application. No desinstala ni cambia nombres técnicos."""

# (technical_name, display_es, application)
CATALOG = (
    ("justech_alexander_admin", "Administración Doralex", True),
    ("justech_alexander_base", "Identidad Doralex", False),
    ("justech_alexander_microsoft_mail", "Correo Microsoft", False),
    ("justech_alexander_reports", "Diseño de reportes Doralex", False),
    ("justech_alexander_website", "Sitio web institucional", False),
    ("justech_alexander_ux", "Experiencia Doralex (menús)", False),
    ("justech_warranty", "Garantías", True),
    ("justech_purchase_sale_margin_control", "Costos y Márgenes", True),
    ("justech_managed_services", "Servicios Administrados", True),
    ("justech_approval_flow", "Aprobaciones", True),
    ("justech_global_audit_log", "Auditoría", False),
    ("justech_fiscal_admin", "Administración Fiscal", False),
    ("l10n_do_ecf_connector", "Conector e-CF DGII", False),
    ("l10n_do_ecf_connector_receptor", "Recepción e-CF proveedor", False),
    ("justech_core", "Utilidades internas", False),
    ("justech_modules", "Registro de módulos", False),
    ("justech_admin_center", "Centro de administración técnica", False),
    ("justech_security_ux", "Permisos y seguridad", False),
    ("justech_mail_outgoing_policy", "Política de correo saliente", False),
    ("justech_report_identity_guard", "Identidad de reportes", False),
    ("justech_sale_terms_guard", "Términos de venta por compañía", False),
    (
        "justech_quotation_client_dedup",
        "Evitar clientes duplicados en cotización",
        False,
    ),
    ("justech_l10n_do_adel_freeze", "Candado de motor fiscal", False),
    ("justech_l10n_do_base", "Base fiscal dominicana", False),
    ("justech_l10n_do_ncf", "NCF", False),
    ("justech_ecf_core", "e-CF", False),
    ("justech_ecf_xml", "e-CF XML", False),
    ("justech_ecf_signature", "e-CF firma", False),
    ("justech_ecf_queue", "e-CF cola", False),
    ("justech_ecf_dgii", "e-CF DGII", False),
    ("justech_ecf_admin", "Administración e-CF", False),
    ("justech_l10n_do_reports", "Reportes fiscales", False),
    ("justech_l10n_do_payments_withholding", "Pagos y retenciones", False),
    ("justech_l10n_do_treasury", "Tesorería", False),
    ("justech_accounting_recovery", "Recuperación contable", False),
    ("justech_l10n_do_hr_payroll", "Nómina", False),
    ("justech_l10n_do_hr_payroll_account", "Nómina — contabilidad", False),
    ("justech_l10n_do_hr_payroll_attendance", "Nómina — asistencia", False),
    ("justech_l10n_do_hr_payroll_bank", "Nómina — pagos bancarios", False),
    ("justech_l10n_do_hr_payroll_holidays", "Nómina — ausencias", False),
    ("justech_l10n_do_hr_payroll_reports", "Nómina — TSS/DGII", False),
    ("justech_l10n_do_hr_payroll_subsidies", "Nómina — subsidios", False),
    ("justech_dgcp_bridge", "Puente DGCP", False),
    ("justech_sale_purchase_trace", "Trazabilidad ventas/compras", False),
    ("justech_vendor_bill_po_control", "Control de facturas proveedor / OC", False),
    ("justech_recurring_fee", "Fees recurrentes", False),
    ("studio_hotfix", "Corrección Studio", False),
    ("l10n_do_accounting", "Contabilidad fiscal (Rep. Dominicana)", False),
    ("multi_invoice_manual_payment_prod", "Pago manual de varias facturas", False),
    ("bi_convert_purchase_from_sales", "Crear compra desde venta", False),
)

VISIBLE_APPS = {
    "justech_alexander_admin",
    "justech_warranty",
    "justech_purchase_sale_margin_control",
    "justech_managed_services",
    "justech_approval_flow",
}


def _apply_catalog(env):
    Module = env["ir.module.module"].sudo()
    for technical, display, application in CATALOG:
        rec = Module.search([("name", "=", technical)], limit=1)
        if not rec:
            continue
        vals = {}
        if rec.application != application:
            vals["application"] = application
        current = rec.with_context(lang="en_US").shortdesc or ""
        if current != display:
            vals["shortdesc"] = display
        if vals:
            rec.write(vals)
        rec.with_context(lang="es_DO").shortdesc = display
        rec.with_context(lang="en_US").shortdesc = display
        if "summary" in rec._fields:
            rec.summary = display


def _apply_menu_names(env):
    renames = {
        "justech_warranty.menu_justech_warranty_root": "Garantías",
        "justech_l10n_do_base.menu_justech_do_fiscal_root": "Fiscal Dominicana",
        "justech_l10n_do_ncf.menu_justech_do_ncf_motor_root": "NCF",
        "justech_l10n_do_reports.menu_justech_do_audit_root": "Reportes fiscales",
        "justech_ecf_core.menu_justech_ecf_root": "e-CF",
        "l10n_do_ecf_connector.ecf_documents_root": "DGII",
        "justech_admin_center.menu_justech_admin_center_root": "Administración técnica",
        "justech_alexander_admin.menu_doralex_modules": "Módulos",
        "justech_approval_flow.menu_justech_approval_root": "Aprobaciones",
    }
    Menu = env["ir.ui.menu"].sudo()
    for xmlid, name in renames.items():
        menu = env.ref(xmlid, raise_if_not_found=False)
        if not menu:
            continue
        menu.with_context(lang="en_US").name = name
        menu.with_context(lang="es_DO").name = name


def post_init_hook(env):
    _apply_catalog(env)
    _apply_menu_names(env)
