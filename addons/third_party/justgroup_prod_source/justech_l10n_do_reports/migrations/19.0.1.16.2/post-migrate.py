"""Reubicar menús Auditoría Fiscal (idempotente, solo metadatos menú)."""
import logging

_logger = logging.getLogger(__name__)

AUDIT_MENU_CHILDREN = [
    ("justech_l10n_do_reports.menu_justech_do_report_606", 10, "606 — Compras"),
    ("justech_l10n_do_reports.menu_justech_do_report_607", 20, "607 — Ventas"),
    ("justech_l10n_do_reports.menu_justech_do_report_608", 30, "608 — Anulados"),
    ("justech_l10n_do_reports.menu_justech_do_report_609", 40, "609 — Pagos al Exterior"),
    ("justech_l10n_do_reports.menu_justech_do_report_623", 50, "623 — Retenciones Estado"),
    ("justech_l10n_do_base.menu_justech_do_document_types", 60, "Tipos de Comprobante"),
    ("justech_l10n_do_ncf.menu_justech_do_ncf_ranges", 70, "Rangos NCF"),
    ("justech_l10n_do_reports.menu_justech_do_audit_consumption", 80, "Consumo NCF"),
    ("justech_l10n_do_reports.menu_justech_do_audit_voided", 90, "NCF Anulados"),
    ("justech_l10n_do_reports.menu_justech_do_audit_history", 100, "Historial Fiscal"),
    ("justech_l10n_do_reports.menu_justech_do_fiscal_review", 110, "Revisión Fiscal"),
    ("justech_l10n_do_reports.menu_justech_do_fiscal_review_pending", 120, "Pendientes de Aprobación"),
    ("justech_l10n_do_reports.menu_justech_do_withholding_catalog", 130, "Administrar Retenciones"),
    ("justech_l10n_do_reports.menu_justech_fiscal_admin_center_audit", 140, "Centro de Administración Fiscal"),
]

HIDE_MENUS = [
    "justech_l10n_do_reports.menu_justech_do_reports_root",
    "justech_l10n_do_reports.menu_justech_do_reports_history",
    "justech_l10n_do_ncf.menu_justech_do_ncf_admin_center",
    "justech_l10n_do_ncf.menu_justech_do_ncf_consumption",
    "justech_l10n_do_ncf.menu_justech_do_ncf_diagnostic",
    "justech_l10n_do_payments_withholding.menu_withholding_catalog",
]


def migrate(cr, version):
    from odoo import api

    env = api.Environment(cr, 1, {})
    audit = env.ref("justech_l10n_do_reports.menu_justech_do_audit_root", raise_if_not_found=False)
    if not audit:
        return
    for xmlid, seq, name in AUDIT_MENU_CHILDREN:
        menu = env.ref(xmlid, raise_if_not_found=False)
        if menu:
            menu.write({"parent_id": audit.id, "sequence": seq, "name": name, "active": True})
    for xmlid in HIDE_MENUS:
        menu = env.ref(xmlid, raise_if_not_found=False)
        if menu:
            menu.write({"active": False})
    _logger.info("justech_l10n_do_reports: menús Auditoría Fiscal consolidados")
