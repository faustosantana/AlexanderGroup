# -*- coding: utf-8 -*-
"""Wizard: Reconciliar numeración fiscal tras sync de datos."""
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError, AccessError


class JustechDoNcfReconcileLine(models.TransientModel):
    _name = "justech.do.ncf.reconcile.line"
    _description = "Línea reconciliación NCF"
    _order = "company_id, prefix"

    wizard_id = fields.Many2one(
        "justech.do.ncf.reconcile.wizard", required=True, ondelete="cascade"
    )
    company_id = fields.Many2one("res.company", readonly=True)
    prefix = fields.Char(readonly=True)
    range_id = fields.Many2one("justech.do.ncf.range", readonly=True)
    current_next = fields.Integer(readonly=True)
    max_published_ncf = fields.Char(readonly=True)
    safe_next = fields.Integer(readonly=True)
    status = fields.Selection(
        selection=[
            ("ok", "Al día"),
            ("advance", "Avanzar"),
            ("blocked", "Bloqueado"),
        ],
        readonly=True,
    )
    selected = fields.Boolean(default=True)
    block_reasons = fields.Text(readonly=True)
    proposal_json = fields.Text(readonly=True)


class JustechDoNcfReconcileWizard(models.TransientModel):
    _name = "justech.do.ncf.reconcile.wizard"
    _description = "Reconciliar numeración fiscal"

    company_ids = fields.Many2many("res.company", string="Empresas")
    line_ids = fields.One2many("justech.do.ncf.reconcile.line", "wizard_id")
    state = fields.Selection(
        selection=[("draft", "Borrador"), ("preview", "Previsualización"), ("done", "Aplicado")],
        default="draft",
        readonly=True,
    )
    result_summary = fields.Text(readonly=True)

    def _check_access(self):
        if not (
            self.env.user.has_group("base.group_system")
            or self.env.user.has_group("justech_l10n_do_base.group_justech_do_fiscal_manager")
        ):
            raise AccessError(
                _("Solo Administrador del sistema o Administrador Fiscal.")
            )

    def action_preview(self):
        self.ensure_one()
        self._check_access()
        self.line_ids.unlink()
        proposals = self.env["justech.do.ncf.reconcile.service"].build_proposals(
            self.company_ids or None
        )
        Line = self.env["justech.do.ncf.reconcile.line"]
        for p in proposals:
            Line.create(
                {
                    "wizard_id": self.id,
                    "company_id": p["company_id"],
                    "prefix": p["prefix"],
                    "range_id": p["range_id"],
                    "current_next": p["current_next"],
                    "max_published_ncf": p.get("max_published_ncf"),
                    "safe_next": p["safe_next"],
                    "status": p["status"],
                    "selected": p["status"] == "advance",
                    "block_reasons": "\n".join(p.get("block_reasons") or []),
                    "proposal_json": json.dumps(p, default=str),
                }
            )
        self.state = "preview"
        return self._reopen()

    def action_apply_selected(self):
        self.ensure_one()
        self._check_access()
        if self.state != "preview":
            raise UserError(_("Debe previsualizar antes de aplicar."))
        service = self.env["justech.do.ncf.reconcile.service"]
        applied = []
        for line in self.line_ids.filtered(lambda l: l.selected and l.status == "advance"):
            proposal = json.loads(line.proposal_json)
            result = service.apply_proposal(proposal)
            applied.append(
                f"{line.company_id.name} {line.prefix}: "
                f"{result['old_next']} → {proposal['safe_next']}"
            )
        self.result_summary = "\n".join(applied) or _("Sin cambios.")
        self.state = "done"
        return self._reopen()

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Reconciliar numeración fiscal"),
            "res_model": "justech.do.ncf.reconcile.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    @api.model
    def action_open_wizard(self):
        return self.create({})._reopen()
