# -*- coding: utf-8 -*-
"""Post-init: sincroniza período YYYYMM y fechas en reportes existentes."""
from __future__ import annotations


def _ensure_audit_under_accountant(env):
    accounting = env.ref("accountant.menu_accounting", raise_if_not_found=False)
    if not accounting:
        return
    audit = env.ref("justech_l10n_do_reports.menu_justech_do_audit_root", raise_if_not_found=False)
    if audit and audit.parent_id != accounting:
        audit.parent_id = accounting


def post_init_hook(env):
    _ensure_audit_under_accountant(env)
    env["justech.do.dgii.tax.classification"].sudo().sync_from_taxes()
    Report = env["justech.do.fiscal.report"].sudo()
    for report in Report.search([]):
        updates = {}
        if not report.period_code and report.date_from:
            updates["period_code"] = report.date_from.strftime("%Y%m")
        if updates:
            report.with_context(justech_skip_state_guard=True).write(updates)
        report._sync_dates_from_period_code()
    if hasattr(Report, "_compute_has_pending_approval"):
        Report.search([])._compute_has_pending_approval()
    if hasattr(Report, "_archive_legacy_reports"):
        Report._archive_legacy_reports()
