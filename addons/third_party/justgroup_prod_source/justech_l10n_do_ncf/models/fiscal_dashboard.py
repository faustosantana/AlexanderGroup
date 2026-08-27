# -*- coding: utf-8 -*-
"""Dashboard fiscal de solo lectura — métricas sobre regularización existente.

No escribe en facturas, NCF, asientos ni reportes DGII al abrirse.
"""
from calendar import monthrange
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


STATUS_608_PENDING = ("pending", "rectification_required", "prepared", "exported")
STATUS_607_PENDING = ("pending", "prepared")
STATUS_IT1_PENDING = ("validation_required", "pending")


class JustechDoFiscalDashboard(models.TransientModel):
    _name = "justech.do.fiscal.dashboard"
    _description = "Dashboard Fiscal (solo lectura)"

    company_id = fields.Many2one(
        "res.company",
        string="Empresa",
        default=lambda self: self.env.company,
    )
    company_ids = fields.Many2many(
        "res.company",
        string="Empresas visibles",
        help="Respetan allowed_company_ids del usuario.",
    )
    filter_all_allowed_companies = fields.Boolean(
        string="Todas mis compañías permitidas",
        default=False,
    )
    filter_responsible_id = fields.Many2one("res.users", string="Responsable")
    filter_period = fields.Char(
        string="Período fiscal (YYYYMM)",
        size=6,
        help="Opcional. Filtra métricas a un período original.",
    )
    responsible_display = fields.Char(
        string="Responsable fiscal (compañía)",
        readonly=True,
    )

    # KPI cards
    kpi_pending_608 = fields.Integer(readonly=True)
    kpi_pending_607 = fields.Integer(readonly=True)
    kpi_pending_it1 = fields.Integer(readonly=True)
    kpi_overdue_activities = fields.Integer(readonly=True)
    kpi_my_activities = fields.Integer(readonly=True)
    kpi_in_progress = fields.Integer(readonly=True)
    kpi_regularized = fields.Integer(readonly=True)
    kpi_observations = fields.Integer(readonly=True)
    kpi_historical_review = fields.Integer(readonly=True)

    period_line_ids = fields.One2many(
        "justech.do.fiscal.dashboard.period",
        "dashboard_id",
        string="Por período",
        readonly=True,
    )
    last_refresh = fields.Datetime(readonly=True)
    notes = fields.Text(
        string="Aviso",
        default=lambda self: _(
            "Vista de solo lectura. Abrir el dashboard no marca reportes "
            "ni crea regularizaciones ni actividades."
        ),
        readonly=True,
    )

    def _allowed_companies(self):
        allowed = self.env.companies
        if not allowed:
            allowed = self.env.company
        return allowed

    def _company_domain(self):
        self.ensure_one()
        if self.filter_all_allowed_companies:
            return [("company_id", "in", self._allowed_companies().ids)]
        company = self.company_id or self.env.company
        if company not in self._allowed_companies():
            raise AccessError(
                _("No tiene acceso a la empresa %(c)s.") % {"c": company.display_name}
            )
        return [("company_id", "=", company.id)]

    def _reg_base_domain(self):
        self.ensure_one()
        domain = list(self._company_domain())
        if self.filter_responsible_id:
            domain.append(("responsible_user_id", "=", self.filter_responsible_id.id))
        if self.filter_period:
            code = (self.filter_period or "").strip()
            if len(code) == 6 and code.isdigit():
                # OR lógico: extend con tres elementos, NUNCA append(a, b, c)
                domain.extend(
                    [
                        "|",
                        ("original_fiscal_period", "=", code),
                        ("reporting_period_608", "=", code),
                    ]
                )
        return domain

    def _count_reg(self, extra_domain):
        Reg = self.env["justech.do.fiscal.regularization"]
        return Reg.search_count(self._reg_base_domain() + extra_domain)

    def _overdue_activity_domain(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        domain = [
            ("res_model", "=", "justech.do.fiscal.regularization"),
            ("date_deadline", "<", today),
        ]
        # Limitar a regularizaciones de compañías permitidas
        regs = self.env["justech.do.fiscal.regularization"].search(
            self._reg_base_domain()
        )
        domain.append(("res_id", "in", regs.ids or [0]))
        if self.filter_responsible_id:
            domain.append(("user_id", "=", self.filter_responsible_id.id))
        return domain

    def _my_activity_domain(self):
        self.ensure_one()
        regs = self.env["justech.do.fiscal.regularization"].search(
            self._reg_base_domain()
        )
        return [
            ("res_model", "=", "justech.do.fiscal.regularization"),
            ("res_id", "in", regs.ids or [0]),
            ("user_id", "=", self.env.user.id),
        ]

    def _historical_mismatch_move_ids(self):
        """NCF anulados con void_date mes ≠ invoice_date; sin backfill."""
        self.ensure_one()
        Move = self.env["account.move"]
        domain = self._company_domain() + [
            ("justech_do_ncf_voided", "=", True),
            ("invoice_date", "!=", False),
            ("justech_do_ncf_void_date", "!=", False),
        ]
        moves = Move.search(domain, limit=2000)
        mismatch_ids = []
        for move in moves:
            inv = move.invoice_date
            void = move.justech_do_ncf_void_date
            if not inv or not void:
                continue
            if (inv.year, inv.month) == (void.year, void.month):
                continue
            # Caso por revisar: sin período 608 persistido o sin regularización
            has_period = bool(
                (move.justech_do_608_reporting_period or "").strip()
                or (move.justech_do_original_fiscal_period or "").strip()
            )
            has_reg = bool(move.justech_do_fiscal_regularization_id)
            if not has_period or not has_reg:
                mismatch_ids.append(move.id)
        return mismatch_ids

    def _format_period_label(self, code):
        code = (code or "").strip()
        if len(code) == 6 and code.isdigit():
            return "%s/%s" % (code[4:6], code[:4])
        return code or "—"

    def _period_bounds(self, period_code):
        code = (period_code or "").strip()
        if len(code) != 6 or not code.isdigit():
            raise UserError(_("Período inválido: %s") % period_code)
        year, month = int(code[:4]), int(code[4:6])
        if month < 1 or month > 12:
            raise UserError(_("Período inválido: %s") % period_code)
        last = monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last)

    def action_refresh(self):
        """Recalcula KPIs y líneas de período (solo transient)."""
        for dash in self:
            dash._refresh_metrics()
        return True

    def _refresh_metrics(self):
        self.ensure_one()
        # No tocar regularizaciones / moves / activities (solo lectura + transient lines)
        company = self.company_id or self.env.company
        resp = company.justech_do_fiscal_regularization_user_id
        vals = {
            "responsible_display": resp.display_name if resp else _("(sin configurar)"),
            "company_ids": [(6, 0, self._allowed_companies().ids)],
            "kpi_pending_608": self._count_reg(
                [
                    ("required_608", "=", True),
                    ("status_608", "in", list(STATUS_608_PENDING)),
                ]
            ),
            "kpi_pending_607": self._count_reg(
                [
                    ("rectification_607_required", "=", True),
                    ("status_607", "in", list(STATUS_607_PENDING)),
                ]
            ),
            "kpi_pending_it1": self._count_reg(
                [
                    ("rectification_it1_required", "=", True),
                    ("status_it1", "in", list(STATUS_IT1_PENDING)),
                ]
            ),
            "kpi_in_progress": self._count_reg([("general_status", "=", "in_progress")]),
            "kpi_regularized": self._count_reg(
                [
                    "|",
                    ("general_status", "=", "regularized"),
                    ("status_608", "=", "accepted"),
                ]
            ),
            "kpi_observations": self._count_reg(
                [
                    "|",
                    ("general_status", "=", "observations"),
                    ("general_status", "=", "review_required"),
                ]
            ),
            "kpi_overdue_activities": self.env["mail.activity"].search_count(
                self._overdue_activity_domain()
            ),
            "kpi_my_activities": self.env["mail.activity"].search_count(
                self._my_activity_domain()
            ),
            "kpi_historical_review": len(self._historical_mismatch_move_ids()),
            "last_refresh": fields.Datetime.now(),
        }
        self.write(vals)
        self.period_line_ids.unlink()
        self._rebuild_period_lines()

    def _rebuild_period_lines(self):
        self.ensure_one()
        Reg = self.env["justech.do.fiscal.regularization"]
        groups = Reg._read_group(
            self._reg_base_domain() + [("original_fiscal_period", "!=", False)],
            groupby=["original_fiscal_period"],
            aggregates=["__count"],
            order="original_fiscal_period DESC",
        )
        lines = []
        seq = 0
        for period, count in groups:
            if not period:
                continue
            seq += 10
            base = self._reg_base_domain() + [("original_fiscal_period", "=", period)]
            lines.append(
                (
                    0,
                    0,
                    {
                        "sequence": seq,
                        "period_code": period,
                        "period_label": self._format_period_label(period),
                        "count_total": count or 0,
                        "count_pending_608": Reg.search_count(
                            base
                            + [
                                ("required_608", "=", True),
                                ("status_608", "in", list(STATUS_608_PENDING)),
                            ]
                        ),
                        "count_pending_607": Reg.search_count(
                            base
                            + [
                                ("rectification_607_required", "=", True),
                                ("status_607", "in", list(STATUS_607_PENDING)),
                            ]
                        ),
                        "count_pending_it1": Reg.search_count(
                            base
                            + [
                                ("rectification_it1_required", "=", True),
                                ("status_it1", "in", list(STATUS_IT1_PENDING)),
                            ]
                        ),
                        "count_in_progress": Reg.search_count(
                            base + [("general_status", "=", "in_progress")]
                        ),
                        "count_regularized": Reg.search_count(
                            base
                            + [
                                "|",
                                ("general_status", "=", "regularized"),
                                ("status_608", "=", "accepted"),
                            ]
                        ),
                    },
                )
            )
        if lines:
            self.write({"period_line_ids": lines})

    @api.model
    def action_open_dashboard(self):
        dash = self.create(
            {
                "company_id": self.env.company.id,
                "filter_all_allowed_companies": False,
            }
        )
        dash._refresh_metrics()
        return {
            "type": "ir.actions.act_window",
            "name": _("Dashboard Fiscal"),
            "res_model": self._name,
            "res_id": dash.id,
            "view_mode": "form",
            "target": "current",
            "context": {"form_view_initial_mode": "readonly"},
        }

    def _open_reg_action(self, name, domain, context=None):
        self.ensure_one()
        full = self._reg_base_domain() + domain
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": "justech.do.fiscal.regularization",
            "view_mode": "list,form",
            "domain": full,
            "context": context or {"create": False, "edit": True},
            "target": "current",
        }

    def action_open_pending_608(self):
        return self._open_reg_action(
            _("Pendientes de 608"),
            [
                ("required_608", "=", True),
                ("status_608", "in", list(STATUS_608_PENDING)),
            ],
        )

    def action_open_pending_607(self):
        return self._open_reg_action(
            _("Rectificativas 607 pendientes"),
            [
                ("rectification_607_required", "=", True),
                ("status_607", "in", list(STATUS_607_PENDING)),
            ],
        )

    def action_open_pending_it1(self):
        return self._open_reg_action(
            _("IT-1 por validar o rectificar"),
            [
                ("rectification_it1_required", "=", True),
                ("status_it1", "in", list(STATUS_IT1_PENDING)),
            ],
        )

    def action_open_in_progress(self):
        return self._open_reg_action(
            _("En proceso"),
            [("general_status", "=", "in_progress")],
        )

    def action_open_regularized(self):
        return self._open_reg_action(
            _("Regularizados"),
            [
                "|",
                ("general_status", "=", "regularized"),
                ("status_608", "=", "accepted"),
            ],
        )

    def action_open_observations(self):
        return self._open_reg_action(
            _("Con observaciones"),
            [
                "|",
                ("general_status", "=", "observations"),
                ("general_status", "=", "review_required"),
            ],
        )

    def action_open_overdue_activities(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Actividades fiscales vencidas"),
            "res_model": "mail.activity",
            "view_mode": "list,form",
            "domain": self._overdue_activity_domain(),
            "target": "current",
        }

    def action_open_my_activities(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Mis actividades fiscales"),
            "res_model": "mail.activity",
            "view_mode": "list,form",
            "domain": self._my_activity_domain(),
            "target": "current",
        }

    def action_open_fiscal_activities(self):
        self.ensure_one()
        regs = self.env["justech.do.fiscal.regularization"].search(
            self._reg_base_domain()
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Actividades fiscales"),
            "res_model": "mail.activity",
            "view_mode": "list,form",
            "domain": [
                ("res_model", "=", "justech.do.fiscal.regularization"),
                ("res_id", "in", regs.ids or [0]),
            ],
            "target": "current",
        }

    def action_open_historical_mismatch(self):
        self.ensure_one()
        Audit = self.env["justech.do.fiscal.dashboard.audit"]
        Audit.search([("create_uid", "=", self.env.user.id)]).unlink()
        lines = []
        Move = self.env["account.move"]
        for move in Move.browse(self._historical_mismatch_move_ids()):
            inv = move.invoice_date
            void = move.justech_do_ncf_void_date
            correct = inv.strftime("%Y%m") if inv else False
            previous = void.strftime("%Y%m") if void else False
            has_reg = bool(move.justech_do_fiscal_regularization_id)
            lines.append(
                {
                    "move_id": move.id,
                    "company_id": move.company_id.id,
                    "ncf": move.justech_do_ncf or False,
                    "invoice_date": inv,
                    "void_date": void,
                    "previous_period": previous,
                    "correct_period": correct,
                    "has_regularization": has_reg,
                    "regularization_id": move.justech_do_fiscal_regularization_id.id,
                    "current_state": move.justech_do_fiscal_regularization_state
                    or move.state,
                    "suggested_action": _(
                        "Revisar manualmente: período correcto %(p)s "
                        "(no corregir en masa)."
                    )
                    % {"p": self._format_period_label(correct)},
                }
            )
        recs = Audit.create(lines) if lines else Audit.browse()
        return {
            "type": "ir.actions.act_window",
            "name": _("Casos históricos por revisar"),
            "res_model": "justech.do.fiscal.dashboard.audit",
            "view_mode": "list,form",
            "domain": [("id", "in", recs.ids)],
            "target": "current",
            "context": {"create": False, "edit": False},
        }

    def action_filter_responsible_configured(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        user = company.justech_do_fiscal_regularization_user_id
        self.write({"filter_responsible_id": user.id if user else False})
        self._refresh_metrics()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_historical_backfill(self):
        """Abre wizard de sincronización histórica (no escribe al abrir)."""
        self.ensure_one()
        return self.env[
            "justech.do.fiscal.historical.backfill.wizard"
        ].action_open_wizard()

    def action_open_608_wizard(self, period_code=None):
        """Abre asistente 608 con período (no presenta ni exporta)."""
        self.ensure_one()
        if self.filter_all_allowed_companies and not period_code:
            raise UserError(
                _(
                    "Seleccione una empresa específica antes de abrir el Formato 608."
                )
            )
        company = self.company_id or self.env.company
        if company not in self._allowed_companies():
            raise AccessError(_("Sin acceso a la empresa seleccionada."))
        code = (period_code or self.filter_period or "").strip()
        if not code:
            raise UserError(_("Indique el período fiscal (YYYYMM) para el 608."))
        date_from, date_to = self._period_bounds(code)
        if "justech.do.fiscal.report.wizard" not in self.env:
            raise UserError(
                _("El módulo de reportes DGII no está disponible en esta base.")
            )
        wiz = self.env["justech.do.fiscal.report.wizard"].create(
            {
                "report_type": "608",
                "company_id": company.id,
                "period_mode": "month",
                "period_code": code,
                "period_year": int(code[:4]),
                "period_month": str(int(code[4:6])),
                "date_from": date_from,
                "date_to": date_to,
            }
        )
        view = self.env.ref(
            "justech_l10n_do_reports.view_justech_do_fiscal_report_wizard",
            raise_if_not_found=False,
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("608 — %(p)s") % {"p": self._format_period_label(code)},
            "res_model": "justech.do.fiscal.report.wizard",
            "res_id": wiz.id,
            "view_mode": "form",
            "views": [(view.id, "form")] if view else [(False, "form")],
            "target": "new",
            "context": {
                "default_report_type": "608",
                "default_company_id": company.id,
                "default_period_code": code,
            },
        }


class JustechDoFiscalDashboardPeriod(models.TransientModel):
    _name = "justech.do.fiscal.dashboard.period"
    _description = "Dashboard fiscal — fila por período"
    _order = "period_code desc, id"

    dashboard_id = fields.Many2one(
        "justech.do.fiscal.dashboard", required=True, ondelete="cascade"
    )
    sequence = fields.Integer(default=10)
    period_code = fields.Char(string="Período", size=6, required=True)
    period_label = fields.Char(string="Período (MM/YYYY)")
    count_total = fields.Integer(string="NCF anulados")
    count_pending_608 = fields.Integer(string="Pendientes 608")
    count_pending_607 = fields.Integer(string="Rectificar 607")
    count_pending_it1 = fields.Integer(string="IT-1 pendiente")
    count_in_progress = fields.Integer(string="En proceso")
    count_regularized = fields.Integer(string="Regularizados")

    def action_open_period_regs(self):
        self.ensure_one()
        dash = self.dashboard_id
        return dash._open_reg_action(
            _("Regularizaciones %(p)s") % {"p": self.period_label},
            [("original_fiscal_period", "=", self.period_code)],
        )

    def action_open_608(self):
        self.ensure_one()
        return self.dashboard_id.action_open_608_wizard(period_code=self.period_code)


class JustechDoFiscalDashboardAudit(models.TransientModel):
    _name = "justech.do.fiscal.dashboard.audit"
    _description = "Auditoría histórica mismatch void_date (solo lectura)"
    _order = "invoice_date desc, id desc"

    move_id = fields.Many2one("account.move", string="Documento", readonly=True)
    company_id = fields.Many2one("res.company", string="Empresa", readonly=True)
    ncf = fields.Char(string="NCF", readonly=True)
    invoice_date = fields.Date(string="Fecha factura", readonly=True)
    void_date = fields.Date(string="Fecha anulación", readonly=True)
    previous_period = fields.Char(string="Período anterior (void)", readonly=True)
    correct_period = fields.Char(string="Período fiscal correcto", readonly=True)
    has_regularization = fields.Boolean(string="Existe regularización", readonly=True)
    regularization_id = fields.Many2one(
        "justech.do.fiscal.regularization", string="Regularización", readonly=True
    )
    current_state = fields.Char(string="Estado actual", readonly=True)
    suggested_action = fields.Char(string="Acción sugerida", readonly=True)

    def action_open_move(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.move_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_regularization(self):
        self.ensure_one()
        if not self.regularization_id:
            raise UserError(_("No hay regularización vinculada."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "justech.do.fiscal.regularization",
            "res_id": self.regularization_id.id,
            "view_mode": "form",
            "target": "current",
        }
