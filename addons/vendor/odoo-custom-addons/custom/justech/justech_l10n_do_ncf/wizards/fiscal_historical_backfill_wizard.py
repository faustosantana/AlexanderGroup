# -*- coding: utf-8 -*-
"""Sincronizar anulaciones históricas → regularizaciones faltantes (preview + execute)."""
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

NCF_RE = re.compile(r"^[BE][0-9]{2}[0-9]{8}$")

BACKFILL_GROUPS = (
    "justech_l10n_do_base.group_justech_do_fiscal_manager",
    "account.group_account_manager",
    "base.group_system",
)


class JustechDoFiscalHistoricalBackfillWizard(models.TransientModel):
    _name = "justech.do.fiscal.historical.backfill.wizard"
    _description = "Sincronizar anulaciones históricas (608)"

    company_id = fields.Many2one(
        "res.company",
        string="Empresa",
        required=True,
        default=lambda self: self.env.company,
    )
    filter_all_allowed_companies = fields.Boolean(
        string="Todas mis compañías permitidas",
        default=False,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("preview", "Vista previa"),
            ("done", "Ejecutado"),
        ],
        default="draft",
        readonly=True,
    )
    line_ids = fields.One2many(
        "justech.do.fiscal.historical.backfill.line",
        "wizard_id",
        string="Candidatos",
    )
    count_analyzed = fields.Integer(readonly=True)
    count_to_create = fields.Integer(readonly=True)
    count_to_review = fields.Integer(readonly=True)
    count_existing = fields.Integer(readonly=True)
    count_skipped = fields.Integer(readonly=True)
    count_created = fields.Integer(readonly=True)
    count_omitted = fields.Integer(readonly=True)
    notes = fields.Text(readonly=True)
    execution_log = fields.Text(readonly=True)

    def _check_backfill_access(self, require_write=False):
        user = self.env.user
        if require_write:
            if not any(user.has_group(g) for g in BACKFILL_GROUPS):
                raise AccessError(
                    _(
                        "Solo Administrador Fiscal, Contable o del Sistema "
                        "pueden crear regularizaciones históricas."
                    )
                )
        else:
            # Vista previa: Responsable Fiscal o superiores
            if not (
                user.has_group("justech_l10n_do_base.group_justech_do_fiscal_user")
                or any(user.has_group(g) for g in BACKFILL_GROUPS)
            ):
                raise AccessError(
                    _("No tiene permiso para auditar anulaciones históricas.")
                )

    def _allowed_companies(self):
        allowed = self.env.companies
        if not allowed:
            allowed = self.env.company
        return allowed

    def _target_companies(self):
        self.ensure_one()
        allowed = self._allowed_companies()
        if self.filter_all_allowed_companies:
            return allowed
        company = self.company_id or self.env.company
        if company not in allowed:
            raise AccessError(
                _("No tiene acceso a la empresa %(c)s.") % {"c": company.display_name}
            )
        return company

    def _voided_move_domain(self, companies):
        # NCF anulado (flag), con o sin state=cancel (p.ej. void directo posted).
        return [
            ("company_id", "in", companies.ids),
            ("justech_do_ncf", "!=", False),
            ("justech_do_ncf_voided", "=", True),
        ]

    def _ncf_prefix(self, ncf):
        ncf = (ncf or "").strip().upper()
        if len(ncf) >= 3:
            return ncf[:3]
        return ""

    def _evaluate_candidate(self, move, svc):
        warnings = []
        ncf = (move.justech_do_ncf or "").strip().upper()
        if hasattr(move, "_justech_get_issued_ncf"):
            issued = move._justech_get_issued_ncf()
            if issued:
                ncf = issued.strip().upper()

        proposed = "skip_ineligible"
        existing = self.env["justech.do.fiscal.regularization"]
        resolved = svc.resolve_original_period(move)
        period = resolved["original_fiscal_period"]
        period_608 = period
        annulment, reason_review = svc.resolve_annulment_type_608(move)
        was_in_607 = resolved["was_in_607"]
        it1 = svc._evaluate_it1_impact(move)

        if not ncf:
            warnings.append(_("Sin NCF"))
            return self._line_vals(
                move, ncf, period, period_608, annulment, was_in_607, it1,
                existing, "skip_ineligible", warnings, resolved,
            )
        if not NCF_RE.match(ncf):
            warnings.append(_("Formato NCF inválido"))
            proposed = "manual_review"
        if not move.justech_do_ncf_voided:
            warnings.append(_("NCF no marcado anulado"))
            return self._line_vals(
                move, ncf, period, period_608, annulment, was_in_607, it1,
                existing, "skip_ineligible", warnings, resolved,
            )
        if move.state not in ("cancel",) and move.justech_do_dgii_fiscal_state != "cancelled":
            if move.state == "posted" and move.justech_do_ncf_voided:
                # Anulación fiscal del NCF sin cancel contable clásica — elegible 608
                warnings.append(_("Posted con NCF anulado (elegible 608)"))
            elif move.state in ("draft",):
                warnings.append(_("Documento en borrador"))
                return self._line_vals(
                    move, ncf, period, period_608, annulment, was_in_607, it1,
                    existing, "skip_ineligible", warnings, resolved,
                )
            else:
                warnings.append(_("Documento activo / no cancelado"))
                return self._line_vals(
                    move, ncf, period, period_608, annulment, was_in_607, it1,
                    existing, "skip_ineligible", warnings, resolved,
                )
        if not move.company_id:
            warnings.append(_("Sin compañía"))
            return self._line_vals(
                move, ncf, period, period_608, annulment, was_in_607, it1,
                existing, "skip_ineligible", warnings, resolved,
            )
        if not period:
            warnings.append(_("Período fiscal no resoluble"))
            return self._line_vals(
                move, ncf, period, period_608, annulment, was_in_607, it1,
                existing, "manual_review", warnings, resolved,
            )

        # Ambigüedad: períodos persistidos distintos
        p_orig = svc._valid_period_code(move.justech_do_original_fiscal_period)
        p_608 = svc._valid_period_code(move.justech_do_608_reporting_period)
        if p_orig and p_608 and p_orig != p_608:
            warnings.append(
                _("Ambigüedad: original %(a)s ≠ 608 %(b)s")
                % {"a": p_orig, "b": p_608}
            )
            return self._line_vals(
                move, ncf, period, period_608, annulment, was_in_607, it1,
                existing, "manual_review", warnings, resolved,
            )

        existing = svc.find_existing_regularization(move, ncf, period)
        if existing:
            return self._line_vals(
                move, ncf, period, period_608, annulment, was_in_607, it1,
                existing, "skip_exists", warnings, resolved,
            )

        if reason_review:
            warnings.append(_("Motivo 608 no determinado — revisión requerida"))
            proposed = "create_review"
        elif resolved["review_required"]:
            warnings.append(_("Período requiere validación"))
            proposed = "create_review"
        elif proposed == "manual_review":
            pass
        else:
            proposed = "create"

        return self._line_vals(
            move, ncf, period, period_608, annulment, was_in_607, it1,
            existing, proposed, warnings, resolved,
        )

    def _line_vals(
        self,
        move,
        ncf,
        period,
        period_608,
        annulment,
        was_in_607,
        it1,
        existing,
        proposed,
        warnings,
        resolved,
    ):
        return {
            "move_id": move.id,
            "company_id": move.company_id.id,
            "ncf": ncf or False,
            "document_type": self._ncf_prefix(ncf) or move.move_type,
            "invoice_date": move.invoice_date,
            "void_date": move.justech_do_ncf_void_date,
            "original_fiscal_period": period or False,
            "reporting_period_608": period_608 or False,
            "was_in_607": was_in_607,
            "rectify_607": bool(was_in_607 and period),
            "evaluate_it1": bool(it1 and period),
            "annulment_type_608": annulment or False,
            "existing_regularization_id": existing.id if existing else False,
            "proposed_action": proposed,
            "period_source": resolved.get("period_source") or False,
            "warnings": " | ".join(warnings) if warnings else False,
            "selected": proposed in ("create", "create_review"),
        }

    def action_preview(self):
        self.ensure_one()
        self._check_backfill_access(require_write=False)
        companies = self._target_companies()
        Move = self.env["account.move"]
        moves = Move.search(self._voided_move_domain(companies), order="invoice_date, id")
        svc = self.env["justech.do.fiscal.regularization.service"]
        self.line_ids.unlink()
        lines = []
        for move in moves:
            lines.append((0, 0, self._evaluate_candidate(move, svc)))
        self.write(
            {
                "line_ids": lines,
                "state": "preview",
                "count_analyzed": len(lines),
                "count_to_create": sum(
                    1 for _, _, v in lines if v["proposed_action"] == "create"
                ),
                "count_to_review": sum(
                    1
                    for _, _, v in lines
                    if v["proposed_action"] in ("create_review", "manual_review")
                ),
                "count_existing": sum(
                    1 for _, _, v in lines if v["proposed_action"] == "skip_exists"
                ),
                "count_skipped": sum(
                    1 for _, _, v in lines if v["proposed_action"] == "skip_ineligible"
                ),
                "notes": _(
                    "Vista previa sin escrituras. Revise filas y pulse "
                    "«Crear regularizaciones faltantes» solo si es consistente."
                ),
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_execute(self):
        self.ensure_one()
        self._check_backfill_access(require_write=True)
        if self.state != "preview":
            raise UserError(_("Ejecute primero la vista previa."))
        svc = self.env["justech.do.fiscal.regularization.service"]
        created = 0
        omitted = 0
        observations = []
        for line in self.line_ids:
            if line.proposed_action not in ("create", "create_review"):
                omitted += 1
                continue
            if not line.selected:
                omitted += 1
                continue
            # Re-evaluar por si cambió algo
            fresh = self._evaluate_candidate(line.move_id, svc)
            if fresh["proposed_action"] not in ("create", "create_review"):
                line.write(
                    {
                        "proposed_action": fresh["proposed_action"],
                        "warnings": fresh.get("warnings"),
                        "selected": False,
                    }
                )
                omitted += 1
                observations.append(
                    "%s → omitido (%s)"
                    % (line.move_id.name, fresh["proposed_action"])
                )
                continue
            if fresh["proposed_action"] == "create_review" and not fresh.get(
                "annulment_type_608"
            ):
                # Crear con review_required (motivo pendiente) — no inventar
                pass
            reg = svc.create_historical_regularization(line.move_id)
            if reg:
                created += 1
                line.write(
                    {
                        "existing_regularization_id": reg.id,
                        "proposed_action": "skip_exists",
                        "selected": False,
                        "warnings": _("Creada id=%s") % reg.id,
                    }
                )
            else:
                omitted += 1
                observations.append("%s → no creada" % line.move_id.name)

        log = _(
            "Usuario: %(u)s | Fecha: %(d)s | Compañía: %(c)s | "
            "Analizados: %(a)s | Creados: %(cr)s | Omitidos: %(o)s"
        ) % {
            "u": self.env.user.display_name,
            "d": fields.Datetime.now(),
            "c": self.company_id.display_name,
            "a": self.count_analyzed,
            "cr": created,
            "o": omitted,
        }
        if observations:
            log = log + "\n" + "\n".join(observations[:50])
        self.write(
            {
                "state": "done",
                "count_created": created,
                "count_omitted": omitted,
                "execution_log": log,
                "notes": _("Ejecución completada. No se presentaron reportes DGII."),
            }
        )
        _logger.info("fiscal_historical_backfill %s", log)
        self._audit_log(created, omitted, log)
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _audit_log(self, created, omitted, log_text):
        if "justech.audit.service" not in self.env:
            return
        try:
            self.env["justech.audit.service"].log_event(
                "fiscal_historical_backfill",
                model=self._name,
                res_id=self.id,
                company=self.company_id,
                details={
                    "analyzed": self.count_analyzed,
                    "created": created,
                    "omitted": omitted,
                    "log": (log_text or "")[:500],
                    "companies": self._target_companies().ids,
                },
            )
        except Exception as exc:  # noqa: BLE001 — no bloquear backfill por auditoría
            _logger.warning("audit log backfill failed: %s", exc)

    @api.model
    def action_open_wizard(self):
        wiz = self.create({"company_id": self.env.company.id})
        return {
            "type": "ir.actions.act_window",
            "name": _("Sincronizar anulaciones históricas"),
            "res_model": self._name,
            "res_id": wiz.id,
            "view_mode": "form",
            "target": "new",
        }


class JustechDoFiscalHistoricalBackfillLine(models.TransientModel):
    _name = "justech.do.fiscal.historical.backfill.line"
    _description = "Línea vista previa backfill histórico"
    _order = "original_fiscal_period desc, ncf"

    wizard_id = fields.Many2one(
        "justech.do.fiscal.historical.backfill.wizard",
        required=True,
        ondelete="cascade",
    )
    selected = fields.Boolean(string="Incluir", default=False)
    company_id = fields.Many2one("res.company", string="Empresa", readonly=True)
    move_id = fields.Many2one("account.move", string="Documento", readonly=True)
    ncf = fields.Char(string="NCF", readonly=True)
    document_type = fields.Char(string="Tipo", readonly=True)
    invoice_date = fields.Date(string="Fecha factura", readonly=True)
    void_date = fields.Date(string="Fecha anulación interna", readonly=True)
    original_fiscal_period = fields.Char(string="Período fiscal original", readonly=True)
    reporting_period_608 = fields.Char(string="Período 608", readonly=True)
    period_source = fields.Char(string="Fuente período", readonly=True)
    was_in_607 = fields.Boolean(string="Incluido anteriormente en 607", readonly=True)
    rectify_607 = fields.Boolean(string="Rectificar 607", readonly=True)
    evaluate_it1 = fields.Boolean(string="Evaluar IT-1", readonly=True)
    annulment_type_608 = fields.Char(string="Motivo 608", readonly=True)
    existing_regularization_id = fields.Many2one(
        "justech.do.fiscal.regularization",
        string="Regularización existente",
        readonly=True,
    )
    proposed_action = fields.Selection(
        selection=[
            ("create", "Crear regularización"),
            ("create_review", "Crear con revisión manual"),
            ("skip_exists", "Ya existe"),
            ("skip_ineligible", "No elegible"),
            ("manual_review", "Revisión manual requerida"),
        ],
        string="Acción propuesta",
        readonly=True,
    )
    warnings = fields.Char(string="Advertencias", readonly=True)
