from odoo import api, fields, models, _
from odoo.exceptions import UserError


class JustechAdminCompanyActivationWizard(models.TransientModel):
    _name = "justech.admin.company.activation.wizard"
    _description = "Activación funcional por empresa"

    line_id = fields.Many2one("justech.admin.module.company", required=True)
    operation = fields.Selection(
        selection=[
            ("activate", "Activar"),
            ("deactivate", "Desactivar"),
            ("engine", "Cambiar motor"),
        ],
        required=True,
        string="Operación",
    )
    product_name = fields.Char(readonly=True, string="Producto")
    module_name = fields.Char(readonly=True, string="Submódulo")
    company_name = fields.Char(readonly=True, string="Empresa")
    before_state = fields.Char(readonly=True, string="Estado actual")
    after_state = fields.Char(readonly=True, string="Estado nuevo")
    before_engine = fields.Char(readonly=True, string="Motor actual")
    after_engine = fields.Char(readonly=True, string="Motor nuevo")
    new_engine = fields.Selection(
        selection=[
            ("traditional_ncf", "NCF tradicional"),
            ("electronic", "Facturación electrónica"),
        ],
        string="Motor fiscal destino",
    )
    enables_text = fields.Text(readonly=True, string="¿Qué habilitará?")
    setup_text = fields.Text(readonly=True, string="Configuración necesaria antes de comenzar")
    risks = fields.Text(readonly=True, string="Riesgos")
    no_impact = fields.Text(readonly=True, string="Qué no se modificará")
    rollback_notes = fields.Text(readonly=True, string="Cómo revertir")
    confirmation = fields.Boolean(string="Confirmo el cambio")
    show_engine = fields.Boolean(compute="_compute_show_engine")

    @api.depends("operation", "line_id", "line_id.module_id.fiscal_engine_capable")
    def _compute_show_engine(self):
        for wiz in self:
            wiz.show_engine = bool(
                wiz.line_id
                and wiz.line_id.module_id.fiscal_engine_capable
                and wiz.operation in ("activate", "engine")
            )

    @api.model
    def action_open(self, line, operation):
        if line.module_id.activation_scope == "global":
            raise UserError(
                _(
                    "%s es global para toda la base. "
                    "No requiere activación por empresa."
                )
                % line.module_id.functional_name
            )
        wiz = self.create({"line_id": line.id, "operation": operation})
        wiz._load_preview()
        title = wiz.product_name or _("Confirmar cambio")
        if operation == "activate":
            title = _("Activar — %s") % (wiz.module_name or title)
        elif operation == "deactivate":
            title = _("Desactivar — %s") % (wiz.module_name or title)
        elif operation == "engine":
            title = _("Cambiar motor — %s") % (wiz.company_name or title)
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": self._name,
            "res_id": wiz.id,
            "view_mode": "form",
            "target": "new",
        }

    @api.onchange("new_engine", "operation")
    def _onchange_preview(self):
        if self.line_id and self.operation:
            self._load_preview()

    def _load_preview(self):
        data = self.env["justech.admin.company.activation.service"].build_preview(
            self.line_id, self.operation, new_engine=self.new_engine
        )
        self.write(
            {
                "product_name": data["product_name"],
                "module_name": data["module_name"],
                "company_name": data["company_name"],
                "before_state": data["before_state"],
                "after_state": data["after_state"],
                "before_engine": data.get("before_engine") or False,
                "after_engine": data.get("after_engine") or False,
                "enables_text": data["enables_text"],
                "setup_text": data["setup_text"],
                "risks": data["risks"],
                "no_impact": data["no_impact"],
                "rollback_notes": data["rollback"],
            }
        )

    def action_apply(self):
        self.ensure_one()
        if not self.confirmation:
            raise UserError(_("Debe confirmar el cambio."))
        self.env["justech.admin.center.auth.service"].require_session()
        label = _("Activar") if self.operation == "activate" else (
            _("Desactivar") if self.operation == "deactivate" else _("Cambiar motor")
        )
        self.env["justech.admin.company.activation.service"].apply(
            self.line_id, self.operation, new_engine=self.new_engine
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Cambio aplicado"),
                "message": _("%(op)s en %(co)s")
                % {"op": label, "co": self.company_name},
                "type": "success",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
