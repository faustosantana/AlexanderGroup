from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class JustechDoNcfConsumption(models.Model):
    _name = "justech.do.ncf.consumption"
    _description = "NCF Consumption Audit"
    _order = "consumption_date desc, id desc"

    range_id = fields.Many2one(
        "justech.do.ncf.range",
        required=True,
        index=True,
        ondelete="restrict",
    )
    move_id = fields.Many2one("account.move", index=True, ondelete="set null")
    ncf = fields.Char(required=True, index=True)
    sequence_number = fields.Integer()
    consumption_date = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
    )
    state = fields.Selection(
        selection=[
            ("consumed", "Consumed"),
            ("voided", "Voided"),
        ],
        default="consumed",
        required=True,
    )
    company_id = fields.Many2one(
        related="range_id.company_id",
        store=True,
        index=True,
    )
    void_user_id = fields.Many2one("res.users", string="Voided By", copy=False)
    void_datetime = fields.Datetime(string="Void Date/Time", copy=False)
    void_reason = fields.Text(string="Void Reason", copy=False)

    def _justech_consumption_engine_mode(self):
        """True solo con contexto técnico explícito del motor NCF."""
        return bool(self.env.context.get("justech_ncf_engine"))

    def _justech_consumption_is_fiscal_manager(self):
        return self.env.user.has_group(
            "justech_l10n_do_base.group_justech_do_fiscal_manager"
        )

    def _justech_check_mutation_allowed(self, operation):
        # create: únicamente motor (contexto justech_ncf_engine), nunca UI manual.
        if operation == "create":
            if self._justech_consumption_engine_mode():
                return
            raise AccessError(
                _(
                    "La auditoría de consumo NCF solo puede crearse desde el motor fiscal."
                )
            )
        # write (anulación): motor o gerente fiscal.
        if operation == "write":
            if self._justech_consumption_engine_mode() or self._justech_consumption_is_fiscal_manager():
                return
            raise AccessError(
                _(
                    "No puede editar la auditoría de consumo NCF. "
                    "Solo el motor fiscal o un gerente fiscal pueden hacerlo."
                )
            )
        # unlink: nunca desde UI.
        raise AccessError(
            _(
                "La auditoría de consumo NCF no puede eliminarse manualmente."
            )
        )

    def _justech_validate_company_consistency(self, vals):
        move_id = vals.get("move_id")
        range_id = vals.get("range_id")
        if not move_id or not range_id:
            return
        move = self.env["account.move"].browse(move_id)
        ncf_range = self.env["justech.do.ncf.range"].browse(range_id)
        if not move.exists() or not ncf_range.exists():
            return
        if move.company_id != ncf_range.company_id:
            raise UserError(
                _(
                    "El consumo NCF debe pertenecer a la misma empresa del documento "
                    "(%(move_co)s ≠ %(range_co)s).",
                    move_co=move.company_id.display_name,
                    range_co=ncf_range.company_id.display_name,
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        self._justech_check_mutation_allowed("create")
        for vals in vals_list:
            self._justech_validate_company_consistency(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._justech_check_mutation_allowed("write")
        return super().write(vals)

    def unlink(self):
        self._justech_check_mutation_allowed("unlink")
        return super().unlink()
