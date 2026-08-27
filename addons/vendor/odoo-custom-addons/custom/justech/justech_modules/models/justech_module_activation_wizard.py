from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..exceptions import JustechLicenseError


class JustechModuleActivationWizard(models.TransientModel):
    _name = "justech.module.activation.wizard"
    _description = "Justech Module Activation Wizard"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    line_ids = fields.One2many(
        "justech.module.activation.wizard.line",
        "wizard_id",
        string="Modules & Features",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            self.env["justech.admin.access.service"].require_session(
                self.env["justech.admin.access.service"].SCOPE_PLATFORM
            )
        records = super().create(vals_list)
        for wizard in records:
            wizard._reload_lines()
        return records

    def _prepare_line_commands(self):
        service = self.env["justech.license.service"]
        catalog = service.get_activation_catalog(company=self.company_id)
        commands = []
        for module_row in catalog:
            dep_names = ", ".join(
                d["module_code"] for d in module_row.get("dependencies", [])
            )
            commands.append(
                {
                    "line_type": "module",
                    "module_code": module_row["module_code"],
                    "display_name": module_row["module_name"],
                    "description": module_row.get("description"),
                    "category": module_row.get("category"),
                    "country": module_row.get("country"),
                    "dependencies_text": dep_names,
                    "required_module": module_row.get("required_module"),
                    "license_required": module_row.get("license_required"),
                    "is_active": module_row.get("is_active"),
                    "activated_at": False,
                    "activated_by_name": False,
                }
            )
            for feat in module_row.get("features", []):
                commands.append(
                    {
                        "line_type": "feature",
                        "module_code": module_row["module_code"],
                        "feature_code": feat["feature_code"],
                        "display_name": feat["feature_name"],
                        "description": feat.get("description"),
                        "category": module_row.get("category"),
                        "country": module_row.get("country"),
                        "dependencies_text": dep_names,
                        "required_module": False,
                        "license_required": feat.get("license_required"),
                        "is_active": feat.get("is_active"),
                        "activated_at": feat.get("activated_at"),
                        "activated_by_name": feat.get("activated_by_name"),
                        "always_on": feat.get("always_on"),
                    }
                )
        return commands

    def _reload_lines(self):
        self.line_ids = [(5, 0, 0)] + [
            (0, 0, vals) for vals in self._prepare_line_commands()
        ]

    def action_refresh(self):
        self.ensure_one()
        self._reload_lines()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    def action_activate_selected(self):
        self.ensure_one()
        if not self.env.context.get("justech_critical_token"):
            return self.env["justech.admin.access.service"].prompt_step_up(
                self._name,
                self.id,
                "_action_activate_selected",
                self.env["justech.admin.access.service"].CRITICAL_PLATFORM_MUTATION,
            )
        return self._action_activate_selected()

    def _action_activate_selected(self):
        self.ensure_one()
        service = self.env["justech.license.service"]
        for line in self.line_ids.filtered("selected"):
            try:
                if line.line_type == "module":
                    service.activate_module(
                        line.module_code, company=self.company_id
                    )
                elif line.feature_code:
                    service.activate_feature(
                        line.feature_code, company=self.company_id
                    )
            except JustechLicenseError as exc:
                raise UserError(str(exc)) from exc
        self._reload_lines()
        return self.action_refresh()

    def action_deactivate_selected(self):
        self.ensure_one()
        if not self.env.context.get("justech_critical_token"):
            return self.env["justech.admin.access.service"].prompt_step_up(
                self._name,
                self.id,
                "_action_deactivate_selected",
                self.env["justech.admin.access.service"].CRITICAL_PLATFORM_MUTATION,
            )
        return self._action_deactivate_selected()

    def _action_deactivate_selected(self):
        self.ensure_one()
        service = self.env["justech.license.service"]
        for line in self.line_ids.filtered("selected"):
            if line.line_type == "feature" and line.always_on:
                raise UserError(
                    _("Feature '%(name)s' is always-on and cannot be deactivated.")
                    % {"name": line.display_name}
                )
            try:
                if line.line_type == "module":
                    service.deactivate_module(
                        line.module_code, company=self.company_id
                    )
                elif line.feature_code:
                    service.deactivate_feature(
                        line.feature_code, company=self.company_id
                    )
            except JustechLicenseError as exc:
                raise UserError(str(exc)) from exc
        self._reload_lines()
        return self.action_refresh()


class JustechModuleActivationWizardLine(models.TransientModel):
    _name = "justech.module.activation.wizard.line"
    _description = "Justech Module Activation Wizard Line"
    _order = "category, module_code, line_type desc, id"

    wizard_id = fields.Many2one(
        "justech.module.activation.wizard",
        required=True,
        ondelete="cascade",
    )
    selected = fields.Boolean(default=False)
    line_type = fields.Selection(
        [("module", "Module"), ("feature", "Feature")],
        required=True,
    )
    module_code = fields.Char()
    feature_code = fields.Char()
    display_name = fields.Char(string="Name")
    description = fields.Text()
    category = fields.Char()
    country = fields.Char()
    dependencies_text = fields.Char(string="Dependencies")
    required_module = fields.Boolean()
    license_required = fields.Boolean()
    always_on = fields.Boolean()
    is_active = fields.Boolean(string="Active")
    activated_at = fields.Datetime()
    activated_by_name = fields.Char(string="Activated By")
