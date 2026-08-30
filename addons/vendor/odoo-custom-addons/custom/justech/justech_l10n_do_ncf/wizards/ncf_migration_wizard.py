# -*- coding: utf-8 -*-
"""Wizard: Migrar numeración fiscal al Motor Justech (preview obligatorio)."""

import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError, AccessError


class JustechDoNcfMigrationLine(models.TransientModel):
    _name = "justech.do.ncf.migration.line"
    _description = "Línea propuesta migración NCF"
    _order = "company_id, prefix"

    wizard_id = fields.Many2one(
        "justech.do.ncf.migration.wizard", required=True, ondelete="cascade"
    )
    company_id = fields.Many2one("res.company", readonly=True)
    prefix = fields.Char(readonly=True)
    document_type_name = fields.Char(string="Tipo", readonly=True)
    max_published_ncf = fields.Char(string="Último NCF publicado", readonly=True)
    legacy_number_next = fields.Integer(string="Siguiente legacy", readonly=True)
    legacy_end = fields.Integer(string="Fin autorizado", readonly=True)
    justech_next = fields.Integer(string="Next Justech actual", readonly=True)
    proposed_next_ncf = fields.Char(string="Nuevo inicio propuesto", readonly=True)
    proposed_end = fields.Integer(string="Hasta", readonly=True)
    status = fields.Selection(
        selection=[
            ("ready", "Listo"),
            ("reconcile", "Requiere reconciliación"),
            ("skip", "Omitir (ya alineado)"),
            ("blocked", "Bloqueado por inconsistencia"),
        ],
        readonly=True,
    )
    selected = fields.Boolean(
        string="Crear / aplicar",
        default=True,
        help="Desmarque para omitir esta línea.",
    )
    block_reasons = fields.Text(string="Detalle", readonly=True)
    proposal_json = fields.Text(readonly=True)

    def action_omit(self):
        self.ensure_one()
        self.selected = False
        return True


class JustechDoNcfMigrationWizard(models.TransientModel):
    _name = "justech.do.ncf.migration.wizard"
    _description = "Migrar numeración fiscal al Motor Justech"

    company_ids = fields.Many2many(
        "res.company",
        string="Empresas",
        help="Vacío = todas las empresas DO con motor Justech activo.",
    )
    line_ids = fields.One2many("justech.do.ncf.migration.line", "wizard_id")
    state = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("preview", "Previsualización"),
            ("done", "Aplicado"),
        ],
        default="draft",
        readonly=True,
    )
    ready_count = fields.Integer(compute="_compute_counts")
    blocked_count = fields.Integer(compute="_compute_counts")
    skip_count = fields.Integer(compute="_compute_counts")
    result_summary = fields.Text(readonly=True)

    @api.depends("line_ids.status")
    def _compute_counts(self):
        for wiz in self:
            wiz.ready_count = len(
                wiz.line_ids.filtered(lambda l: l.status in ("ready", "reconcile"))
            )
            wiz.blocked_count = len(
                wiz.line_ids.filtered(lambda l: l.status == "blocked")
            )
            wiz.skip_count = len(wiz.line_ids.filtered(lambda l: l.status == "skip"))

    def _check_access(self, operation: str):
        """Odoo 19: BaseModel._check_access(self, operation) → None | (records, factory)."""
        result = super()._check_access(operation)
        if result:
            return result
        if not (
            self.env.user.has_group("base.group_system")
            or self.env.user.has_group(
                "justech_l10n_do_base.group_justech_do_fiscal_manager"
            )
        ):

            def _make_error():
                return AccessError(
                    _(
                        "Solo Administrador del sistema o Administrador Fiscal "
                        "pueden migrar la numeración NCF."
                    )
                )

            return self, _make_error
        return None

    def action_preview(self):
        self.ensure_one()
        self.check_access("write")
        self.line_ids.unlink()
        companies = self.company_ids or None
        proposals = self.env["justech.do.ncf.migration.service"].build_proposals(
            companies
        )
        Line = self.env["justech.do.ncf.migration.line"]
        for p in proposals:
            Line.create(
                {
                    "wizard_id": self.id,
                    "company_id": p["company_id"],
                    "prefix": p["prefix"],
                    "document_type_name": p.get("document_type_name"),
                    "max_published_ncf": p.get("max_published_ncf"),
                    "legacy_number_next": p.get("legacy_number_next"),
                    "legacy_end": p.get("legacy_end"),
                    "justech_next": p.get("justech_next") or 0,
                    "proposed_next_ncf": p.get("proposed_next_ncf"),
                    "proposed_end": p.get("proposed_end"),
                    "status": p["status"],
                    "selected": p["status"] in ("ready", "reconcile"),
                    "block_reasons": "\n".join(p.get("block_reasons") or []),
                    "proposal_json": json.dumps(p, default=str),
                }
            )
        self.state = "preview"
        return self._reopen()

    def action_apply_selected(self):
        self.ensure_one()
        self.check_access("write")
        if self.state != "preview":
            raise UserError(_("Debe previsualizar antes de aplicar."))
        service = self.env["justech.do.ncf.migration.service"]
        applied = []
        for line in self.line_ids.filtered(
            lambda l: l.selected and l.status in ("ready", "reconcile")
        ):
            proposal = json.loads(line.proposal_json)
            result = service.apply_proposal(proposal, enable_journals=True)
            applied.append(
                f"{line.company_id.name} {line.prefix} → rango {result['range'].id} "
                f"next={proposal['safe_next']} journals+={result['journals_enabled']}"
            )
            line.selected = False
            line.status = "skip"
            line.block_reasons = (
                _("Aplicado.") + "\n" + (line.block_reasons or "")
            ).strip()
        self.result_summary = "\n".join(applied) or _("No se aplicó ninguna línea.")
        self.state = "done"
        return self._reopen()

    def action_cancel(self):
        return {"type": "ir.actions.act_window_close"}

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Migrar numeración fiscal al Motor Justech"),
            "res_model": "justech.do.ncf.migration.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    @api.model
    def action_open_wizard(self):
        wiz = self.create({})
        return wiz._reopen()
