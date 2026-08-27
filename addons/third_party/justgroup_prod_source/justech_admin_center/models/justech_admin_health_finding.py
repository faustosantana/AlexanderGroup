from odoo import api, fields, models, _


class JustechAdminHealthFinding(models.Model):
    _name = "justech.admin.health.finding"
    _description = "Pendiente / hallazgo Justech Admin"
    _order = "severity_rank desc, id desc"
    _rec_name = "name"

    name = fields.Char(required=True, string="Título")
    code = fields.Char(required=True, index=True)
    module_id = fields.Many2one(
        "justech.admin.module", ondelete="cascade", string="Submódulo", index=True
    )
    product_id = fields.Many2one(
        related="module_id.product_id",
        store=True,
        index=True,
        string="Producto",
    )
    severity = fields.Selection(
        selection=[
            ("info", "Informativo"),
            ("warning", "Advertencia"),
            ("error", "Error"),
            ("critical", "Crítico"),
        ],
        default="warning",
        required=True,
        string="Severidad",
    )
    severity_rank = fields.Integer(compute="_compute_severity_rank", store=True)
    state = fields.Selection(
        selection=[
            ("open", "Pendiente"),
            ("in_progress", "En proceso"),
            ("resolved", "Resuelto"),
            ("ignored", "Ignorado"),
        ],
        default="open",
        required=True,
        string="Estado",
    )
    detail = fields.Text(string="Descripción")
    impact = fields.Text(string="Impacto")
    recommendation = fields.Text(string="Acción necesaria")
    action_label = fields.Char(string="Etiqueta de acción", default="Resolver")
    responsible_hint = fields.Char(string="Responsable recomendado")
    ignore_reason = fields.Text(string="Justificación al ignorar")
    detected_at = fields.Datetime(default=fields.Datetime.now, string="Detectado")
    owner_id = fields.Many2one("res.users", string="Responsable")
    res_model = fields.Char()
    res_id = fields.Integer()
    company_id = fields.Many2one("res.company", string="Empresa", index=True)
    resolve_xmlid = fields.Char(
        help="Acción XMLID preferida al resolver (sin exponer en UI).",
    )

    @api.depends("severity")
    def _compute_severity_rank(self):
        rank = {"critical": 40, "error": 30, "warning": 20, "info": 10}
        for rec in self:
            rec.severity_rank = rank.get(rec.severity, 0)

    def action_open_record(self):
        self.ensure_one()
        if not self.res_model or not self.res_id:
            return self.action_resolve()
        return {
            "type": "ir.actions.act_window",
            "name": self.name,
            "res_model": self.res_model,
            "res_id": self.res_id,
            "view_mode": "form",
            "target": "current",
        }

    def action_mark_in_progress(self):
        self.write({"state": "in_progress"})
        return True

    def action_mark_resolved(self):
        self.write({"state": "resolved"})
        return True

    def action_mark_ignored(self):
        self.ensure_one()
        if not self.ignore_reason:
            return {
                "type": "ir.actions.act_window",
                "name": _("Ignorar con justificación"),
                "res_model": self._name,
                "res_id": self.id,
                "view_mode": "form",
                "target": "new",
                "context": {"form_view_initial_mode": "edit"},
            }
        self.write({"state": "ignored"})
        return True

    def action_resolve(self):
        """Abre la pantalla correcta para corregir el pendiente (página completa)."""
        self.ensure_one()
        gate = self.env["justech.admin.center.auth.service"].gate_or_wizard()
        if gate:
            return gate
        self.write({"state": "in_progress"})
        if self.resolve_xmlid:
            try:
                act = self.env.ref(self.resolve_xmlid)
                if act._name == "ir.actions.server":
                    return act.run()
                data = act.read()[0]
                data.pop("id", None)
                data["target"] = "current"
                return data
            except ValueError:
                pass
        if self.res_model and self.res_id:
            return self.action_open_record()
        if self.module_id:
            return self.module_id.action_configure()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sin acción directa"),
                "message": self.recommendation or _("Revise la configuración del producto."),
                "type": "warning",
            },
        }

    def action_open_config(self):
        self.ensure_one()
        if self.module_id:
            return self.module_id.action_configure()
        return self.action_resolve()
