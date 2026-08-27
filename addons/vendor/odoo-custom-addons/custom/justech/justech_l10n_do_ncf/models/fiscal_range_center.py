"""Centro único de administración fiscal (menú Rangos).

Unifica Ventas / Compras Emitidas / Compras Recibidas sin menús duplicados.
No inventa rangos ni consume secuencias.
Capa UX (Release 2026.2): clasificación Uso, filtros y badges — sin lógica fiscal.
"""
from odoo import _, api, fields, models

_DocType = "justech.do.fiscal.document.type"
_RECEIVED_PREFIXES = (
    "B01",
    "B02",
    "B03",
    "B04",
    "B14",
    "B15",
    "B16",
    "E31",
    "E32",
    "E33",
    "E34",
    "E41",
    "E43",
    "E44",
    "E45",
    "E46",
    "E47",
)
_PURCHASE_ISSUED = ("B11", "B13", "B17")

# Etiqueta de negocio para tipos LATAM sin company_id (no son rangos DGII).
_RECEIVED_COMPANY_LABEL = "Compras recibidas — no consumen secuencia"

_UX_STATUS_LABELS = {
    "active": "Activo",
    "inactive": "Inactivo",
    "expired": "Vencido",
    "depleted": "Agotado",
    "draft": "Borrador",
    "no_range": "Sin rango",
    "no_range_needed": "No requiere rango",
    "cancelled": "Inactivo",
}


class JustechDoFiscalRangeCenter(models.Model):
    _name = "justech.do.fiscal.range.center"
    _description = "Centro de Administración Fiscal — Rangos"
    _rec_name = "name"

    name = fields.Char(default="Rangos", readonly=True)
    flow_filter = fields.Selection(
        selection=[
            ("all", "Todos"),
            ("sale", "Ventas"),
            ("purchase_received", "Compras Recibidas"),
            ("purchase_issued", "Compras Emitidas"),
            ("company", "Rangos propios (empresa)"),
        ],
        string="Uso",
        default="company",
        required=True,
        help="Clasificación funcional de la vista. No altera rangos ni secuencias.",
    )
    status_filter = fields.Selection(
        selection=[
            ("all", "Todos"),
            ("active", "Activos"),
            ("inactive", "Inactivos"),
            ("expired", "Vencidos"),
            ("depleted", "Agotados"),
            ("draft", "Borrador"),
        ],
        string="Estado",
        default="all",
        required=True,
    )
    medium_filter = fields.Selection(
        selection=[
            ("all", "Todos"),
            ("physical", "Físicos"),
            ("electronic", "Electrónicos"),
        ],
        string="Tipo",
        default="all",
        required=True,
    )
    filter_company_id = fields.Many2one(
        "res.company",
        string="Empresa",
        help="Filtro UX opcional. Vacío = empresas del selector multiempresa.",
    )
    line_ids = fields.One2many(
        "justech.do.fiscal.range.center.line",
        "center_id",
        string="Tipos",
    )
    # Vista filtrada (solo presentación; no altera line_ids ni rangos reales)
    filtered_line_ids = fields.Many2many(
        "justech.do.fiscal.range.center.line",
        compute="_compute_filtered_line_ids",
        string="Tipos visibles",
    )
    # KPI (misma estructura para las 3 tarjetas)
    sale_types_count = fields.Integer(compute="_compute_kpis")
    sale_active_count = fields.Integer(compute="_compute_kpis")
    sale_pending_count = fields.Integer(compute="_compute_kpis")
    sale_no_range_count = fields.Integer(compute="_compute_kpis")
    issued_types_count = fields.Integer(compute="_compute_kpis")
    issued_active_count = fields.Integer(compute="_compute_kpis")
    issued_pending_count = fields.Integer(compute="_compute_kpis")
    issued_no_range_count = fields.Integer(compute="_compute_kpis")
    received_types_count = fields.Integer(compute="_compute_kpis")
    received_active_count = fields.Integer(compute="_compute_kpis")
    received_pending_count = fields.Integer(compute="_compute_kpis")
    received_no_range_count = fields.Integer(compute="_compute_kpis")

    def _kpi_company_ids(self):
        """Empresas visibles según selector multiempresa (allowed_company_ids)."""
        return set(self.env.companies.ids)

    def _ux_company_ids(self):
        """Empresas para filtro UX (selector opcional o multiempresa)."""
        self.ensure_one()
        if self.filter_company_id:
            return {self.filter_company_id.id}
        return self._kpi_company_ids()

    @api.depends(
        "line_ids",
        "line_ids.flow",
        "line_ids.ux_status",
        "line_ids.document_medium",
        "line_ids.company_id",
        "flow_filter",
        "status_filter",
        "medium_filter",
        "filter_company_id",
    )
    def _compute_filtered_line_ids(self):
        for center in self:
            lines = center.line_ids
            flow = center.flow_filter or "company"
            if flow == "company":
                allowed = center._ux_company_ids()
                lines = lines.filtered(
                    lambda l, a=allowed: l.flow in ("sale", "purchase_issued")
                    and l.company_id.id in a
                )
            elif flow == "all":
                allowed = center._ux_company_ids()
                lines = lines.filtered(
                    lambda l, a=allowed: l.flow == "purchase_received"
                    or (l.company_id and l.company_id.id in a)
                )
            elif flow in ("sale", "purchase_issued"):
                allowed = center._ux_company_ids()
                lines = lines.filtered(
                    lambda l, f=flow, a=allowed: l.flow == f and l.company_id.id in a
                )
            elif flow == "purchase_received":
                lines = lines.filtered(lambda l: l.flow == "purchase_received")

            status = center.status_filter or "all"
            if status == "inactive":
                lines = lines.filtered(
                    lambda l: l.ux_status in ("inactive", "cancelled", "no_range")
                )
            elif status != "all":
                lines = lines.filtered(lambda l, s=status: l.ux_status == s)

            medium = center.medium_filter or "all"
            if medium != "all":
                lines = lines.filtered(lambda l, m=medium: l.document_medium == m)

            center.filtered_line_ids = lines

    @api.depends(
        "line_ids",
        "line_ids.flow",
        "line_ids.ux_status",
        "line_ids.active_flag",
        "line_ids.company_id",
    )
    def _compute_kpis(self):
        for center in self:
            allowed = center._kpi_company_ids()
            sales = center.line_ids.filtered(
                lambda l: l.flow == "sale" and l.company_id.id in allowed
            )
            issued = center.line_ids.filtered(
                lambda l: l.flow == "purchase_issued" and l.company_id.id in allowed
            )
            received = center.line_ids.filtered(lambda l: l.flow == "purchase_received")
            center.sale_types_count = len(sales)
            center.sale_active_count = len(
                sales.filtered(lambda l: l.ux_status == "active")
            )
            center.sale_pending_count = len(
                sales.filtered(
                    lambda l: l.ux_status
                    in ("inactive", "draft", "expired", "depleted", "cancelled")
                )
            )
            center.sale_no_range_count = len(
                sales.filtered(lambda l: l.ux_status == "no_range")
            )
            center.issued_types_count = len(issued)
            center.issued_active_count = len(
                issued.filtered(lambda l: l.ux_status == "active")
            )
            center.issued_pending_count = len(
                issued.filtered(
                    lambda l: l.ux_status
                    in ("inactive", "draft", "expired", "depleted", "cancelled")
                )
            )
            center.issued_no_range_count = len(
                issued.filtered(lambda l: l.ux_status == "no_range")
            )
            center.received_types_count = len(received)
            center.received_active_count = len(
                received.filtered(lambda l: l.active_flag)
            )
            center.received_pending_count = len(
                received.filtered(lambda l: not l.active_flag)
            )
            # Recibidos nunca tienen rango Justech
            center.received_no_range_count = 0

    @api.model
    def get_or_create(self):
        center = self.sudo().search([], limit=1)
        if not center:
            center = self.sudo().create({"name": "Rangos"})
        center.sudo().refresh_lines()
        return center

    def refresh_lines(self):
        """Reconstruye filas administrativas sin inventar rangos ni NCF.

        Mantiene caché multiempresa completa para no borrar líneas de otras
        empresas al refrescar. La vista filtra por allowed_company_ids.
        """
        self.ensure_one()
        Line = self.env["justech.do.fiscal.range.center.line"].sudo()
        existing = {(l.flow, l.company_id.id or 0, l.prefix): l for l in self.line_ids}
        keep = set()
        vals_list = []

        DocType = self.env[_DocType]
        # Caché completa: todas las empresas (la UI filtra por env.companies).
        companies = self.env["res.company"].sudo().search([])
        Range = self.env["justech.do.ncf.range"]
        Config = self.env["justech.do.purchase.emission.config"]
        Latam = self.env["l10n_latam.document.type"]

        # Ventas: tipos venta × empresa + rango activo si existe
        sale_docs = DocType.search([("is_sale_document", "=", True)])
        for company in companies:
            for doc in sale_docs:
                prefix = doc.prefix
                key = ("sale", company.id, prefix)
                keep.add(key)
                rng = Range.search(
                    [
                        ("company_id", "=", company.id),
                        ("document_type_id", "=", doc.id),
                        ("state", "=", "active"),
                    ],
                    order="date_to desc, id desc",
                    limit=1,
                )
                # Fallback UX: si el catálogo y el rango divergen por document_type_id,
                # resolver por prefijo (no altera secuencias ni crea rangos).
                if not rng:
                    rng = Range.search(
                        [
                            ("company_id", "=", company.id),
                            ("prefix", "=", prefix),
                            ("state", "=", "active"),
                        ],
                        order="date_to desc, id desc",
                        limit=1,
                    )
                if not rng:
                    rng = Range.search(
                        [
                            ("company_id", "=", company.id),
                            ("document_type_id", "=", doc.id),
                        ],
                        order="date_to desc, id desc",
                        limit=1,
                    )
                if not rng:
                    rng = Range.search(
                        [
                            ("company_id", "=", company.id),
                            ("prefix", "=", prefix),
                        ],
                        order="date_to desc, id desc",
                        limit=1,
                    )
                payload = self._vals_from_range(
                    flow="sale",
                    company=company,
                    prefix=prefix,
                    name=doc.name,
                    origin="justech",
                    consumes=True,
                    rng=rng,
                    document_type=doc,
                )
                active_count = Range.search_count(
                    [
                        ("company_id", "=", company.id),
                        ("prefix", "=", prefix),
                        ("state", "=", "active"),
                    ]
                )
                if active_count > 1:
                    payload["status_label"] = _(
                        "Advertencia: %(n)s rangos activos — revise inconsistencia"
                    ) % {"n": active_count}
                payload["last_used"] = self._last_used_for_prefix(
                    company=company, prefix=prefix, move_types=("out_invoice", "out_refund")
                )
                vals_list.append((key, payload))

        # Compras emitidos: configs existentes B11/B13/B17 (no crear filas nuevas aquí).
        # ensure_configs queda fuera del refresh de vista para no crear metadatos al abrir.
        configs = Config.search(
            [
                ("company_id", "in", companies.ids),
                ("prefix", "in", list(_PURCHASE_ISSUED)),
            ]
        )
        for cfg in configs:
            prefix = cfg.prefix
            if prefix not in _PURCHASE_ISSUED:
                continue
            key = ("purchase_issued", cfg.company_id.id, prefix)
            keep.add(key)
            rng = cfg.range_id
            if rng:
                ux_status, ux_label = self._ux_status_from_range(rng)
            else:
                ux_status = cfg.status or "no_range"
                ux_label = cfg.status_label or _UX_STATUS_LABELS.get(
                    ux_status, "Sin rango autorizado"
                )
            is_electronic = prefix.startswith("E")
            payload = {
                "center_id": self.id,
                "flow": "purchase_issued",
                "company_id": cfg.company_id.id,
                "prefix": prefix,
                "code": cfg.code or prefix[-2:],
                "name": cfg.name_full or cfg.document_type_id.name,
                "origin": "justech",
                "consumes_sequence": True,
                "status": ux_status,
                "status_label": ux_label,
                "active_flag": ux_status == "active",
                "range_id": rng.id if rng else False,
                "emission_config_id": cfg.id,
                "document_type_id": cfg.document_type_id.id,
                "sequence_start": cfg.sequence_start or 0,
                "sequence_end": cfg.sequence_end or 0,
                "next_sequence": rng.next_sequence if rng else 0,
                "next_ncf": cfg.next_ncf or False,
                "remaining_count": rng.remaining_count if rng else 0,
                "date_from": cfg.authorization_date,
                "date_to": cfg.expiration_date,
                "journal_names": ", ".join(rng.journal_ids.mapped("name"))
                if rng
                else False,
                "document_medium": "electronic" if is_electronic else "physical",
                "document_category": "e-CF" if is_electronic else "B",
                "is_electronic_supplier": is_electronic,
                "participates_606": True,
                "participates_607": False,
                "participates_608": True,
                "participates_609": prefix == "B17",
                "participates_623": False,
                "last_used": self._last_used_for_prefix(
                    company=cfg.company_id,
                    prefix=prefix,
                    move_types=("in_invoice", "in_refund"),
                ),
            }
            vals_list.append((key, payload))

        # Documentos recibidos: tipos LATAM compartidos (sin company_id / sin rango propio)
        latam_types = Latam.search([("doc_code_prefix", "in", list(_RECEIVED_PREFIXES))])
        for latam in latam_types:
            prefix = (latam.doc_code_prefix or "").strip().upper()
            key = ("purchase_received", 0, prefix)
            keep.add(key)
            usage = 0
            last_used = False
            if "justech_do_usage_count" in latam._fields:
                usage = latam.justech_do_usage_count
                last_used = latam.justech_do_last_used
            else:
                Move = self.env["account.move"]
                domain = [
                    ("l10n_latam_document_type_id", "=", latam.id),
                    ("move_type", "in", ("in_invoice", "in_refund")),
                ]
                usage = Move.search_count(domain)
                last = Move.search(domain, order="write_date desc", limit=1)
                last_used = last.write_date if last else False
            is_ecf = prefix.startswith("E")
            ux_status = "active" if latam.active else "inactive"
            payload = {
                "center_id": self.id,
                "flow": "purchase_received",
                "company_id": False,
                "prefix": prefix,
                "code": prefix[1:] if len(prefix) == 3 else prefix,
                "name": latam.name,
                "origin": "latam",
                "consumes_sequence": False,
                "status": ux_status,
                "status_label": _UX_STATUS_LABELS[ux_status],
                "active_flag": bool(latam.active),
                "latam_document_type_id": latam.id,
                "usage_count": usage,
                "last_used": last_used,
                "is_electronic_supplier": is_ecf,
                "is_received_document": True,
                "document_category": "e-CF" if is_ecf else "B",
                "document_medium": "electronic" if is_ecf else "physical",
                "participates_606": True,
                "participates_607": False,
                "participates_608": False,
                "participates_609": False,
                "participates_623": False,
                "help_text": (
                    "NCF de proveedores (configuración general LATAM). "
                    "El NCF lo aporta el proveedor; no consume rangos ni secuencias Justech. "
                    "Badge Activo/Inactivo refleja el tipo LATAM, no un rango Justech."
                ),
            }
            vals_list.append((key, payload))

        for key, payload in vals_list:
            rec = existing.get(key)
            if rec:
                rec.write(payload)
            else:
                Line.create(payload)

        for key, rec in existing.items():
            if key not in keep:
                rec.unlink()
        return True

    def _ux_status_from_range(self, rng):
        """Estado de presentación para el Centro. No escribe justech.do.ncf.range."""
        if not rng:
            return "no_range", _UX_STATUS_LABELS["no_range"]
        today = fields.Date.context_today(self)
        stored = rng.state
        remaining = getattr(rng, "remaining_count", None)
        if remaining is None:
            remaining = max(int(rng.sequence_end) - int(rng.next_sequence) + 1, 0)

        # Estado operativo de presentación (solo UI del Centro).
        if stored == "cancelled":
            ux = "inactive"
        elif stored == "draft":
            ux = "draft"
        elif stored == "expired" or (rng.date_to and today > rng.date_to):
            ux = "expired"
        elif stored == "depleted" or remaining <= 0:
            ux = "depleted"
        elif stored == "active":
            ux = "active"
        else:
            ux = stored

        label = _UX_STATUS_LABELS.get(ux, ux)
        # Avisos suaves sin cambiar el badge principal.
        if ux == "active":
            if remaining and remaining <= max(
                int((rng.sequence_end - rng.sequence_start + 1) * 0.1), 10
            ):
                label = "Activo (agotándose)"
            elif rng.date_to and (rng.date_to - today).days <= 30:
                label = "Activo (próximo a vencer)"
        return ux, label

    def _vals_from_range(
        self, flow, company, prefix, name, origin, consumes, rng, document_type
    ):
        status, status_label = self._ux_status_from_range(rng)
        is_electronic = (prefix or "").upper().startswith("E")
        return {
            "center_id": self.id,
            "flow": flow,
            "company_id": company.id,
            "prefix": prefix,
            "code": document_type.code if document_type else prefix[-2:],
            "name": name,
            "origin": origin,
            "consumes_sequence": consumes,
            "status": status,
            "status_label": status_label,
            "active_flag": status == "active",
            "range_id": rng.id if rng else False,
            "document_type_id": document_type.id if document_type else False,
            "sequence_start": rng.sequence_start if rng else 0,
            "sequence_end": rng.sequence_end if rng else 0,
            "next_sequence": rng.next_sequence if rng else 0,
            "next_ncf": rng.next_ncf_display if rng else False,
            "remaining_count": rng.remaining_count if rng else 0,
            "date_from": rng.date_from if rng else False,
            "date_to": rng.date_to if rng else False,
            "journal_names": ", ".join(rng.journal_ids.mapped("name")) if rng else False,
            "document_medium": "electronic" if is_electronic else "physical",
            "document_category": "e-CF" if is_electronic else "B",
            "is_electronic_supplier": is_electronic,
            "participates_606": False,
            "participates_607": True,
            "participates_608": True,
            "participates_609": False,
            "participates_623": False,
        }

    @api.onchange("flow_filter", "status_filter", "medium_filter", "filter_company_id")
    def _onchange_ux_filters(self):
        # Los filtros son de presentación; filtered_line_ids se recalcula por depends.
        return

    def _last_used_for_prefix(self, company, prefix, move_types):
        """Lectura operativa: no escribe histórico ni consume NCF."""
        Move = self.env["account.move"].sudo()
        domain = [
            ("company_id", "=", company.id),
            ("state", "=", "posted"),
            ("move_type", "in", list(move_types)),
            ("justech_do_ncf", "=ilike", f"{prefix}%"),
        ]
        last = Move.search(domain, order="write_date desc, id desc", limit=1)
        return last.write_date if last else False

    def action_refresh(self):
        """Recalcula la vista administrativa. No altera rangos, secuencias ni NCF."""
        self.ensure_one()
        self.sudo().refresh_lines()
        return self.action_open()

    def action_open_advanced_list(self):
        """Lista buscable/agrupable de líneas del Centro (solo lectura)."""
        self.ensure_one()
        self.sudo().refresh_lines()
        return {
            "type": "ir.actions.act_window",
            "name": _("Centro de Rangos — Lista"),
            "res_model": "justech.do.fiscal.range.center.line",
            "view_mode": "list,form",
            "domain": [("center_id", "=", self.id)],
            "context": {"search_default_group_company": 1},
            "target": "current",
        }

    @api.model
    def action_validate_range_states_readonly(self):
        """Valida estados almacenados vs esperados. No corrige nada.

        Returns list of dicts: range, cause, expected, actual.
        """
        Range = self.env["justech.do.ncf.range"].sudo()
        anomalies = []
        today = fields.Date.context_today(self)
        for rng in Range.search([]):
            expected = rng._compute_target_state()
            actual = rng.state
            if expected == actual:
                continue
            if actual == "active" and expected == "expired":
                cause = "date_to vencida y state sigue active"
            elif actual == "active" and expected == "depleted":
                cause = "sin disponibles y state sigue active"
            elif actual != expected:
                cause = f"state almacenado ({actual}) ≠ operativo ({expected})"
            else:
                cause = "desajuste de estado"
            anomalies.append(
                {
                    "range_id": rng.id,
                    "range": f"{rng.display_name} [{rng.prefix}] "
                    f"{rng.company_id.display_name}",
                    "cause": cause,
                    "estado_esperado": expected,
                    "estado_actual": actual,
                    "date_to": str(rng.date_to or ""),
                    "remaining_count": rng.remaining_count,
                    "as_of": str(today),
                }
            )
        return anomalies

    @api.model
    def action_open(self):
        center = self.get_or_create()
        # Defaults UX: rangos propios de empresas activas.
        vals = {}
        if center.flow_filter not in (
            "company",
            "sale",
            "purchase_issued",
            "purchase_received",
            "all",
        ):
            vals["flow_filter"] = "company"
        if not center.status_filter:
            vals["status_filter"] = "all"
        if not center.medium_filter:
            vals["medium_filter"] = "all"
        if vals:
            center.sudo().write(vals)
        return {
            "type": "ir.actions.act_window",
            "name": _("Rangos"),
            "res_model": self._name,
            "res_id": center.id,
            "view_mode": "form",
            "target": "current",
            "context": {
                "form_view_initial_mode": "edit",
                "default_flow_filter": "company",
                "default_status_filter": "all",
                "default_medium_filter": "all",
            },
        }


class JustechDoFiscalRangeCenterLine(models.Model):
    _name = "justech.do.fiscal.range.center.line"
    _description = "Línea del Centro de Rangos Fiscales"
    _order = "flow, company_id, prefix"
    _rec_name = "display_name_ux"

    center_id = fields.Many2one(
        "justech.do.fiscal.range.center",
        required=True,
        ondelete="cascade",
        index=True,
    )
    flow = fields.Selection(
        selection=[
            ("sale", "Ventas"),
            ("purchase_issued", "Compras Emitidas"),
            ("purchase_received", "Compras Recibidas"),
        ],
        string="Uso",
        required=True,
        index=True,
    )
    company_id = fields.Many2one("res.company", string="Empresa", index=True)
    company_display = fields.Char(compute="_compute_company_display", store=True)
    prefix = fields.Char(string="Código", required=True, index=True)
    code = fields.Char(string="Código corto")
    name = fields.Char(string="Nombre legal", required=True)
    display_name_ux = fields.Char(
        string="Resumen",
        compute="_compute_display_name_ux",
    )
    origin = fields.Selection(
        selection=[
            ("justech", "Motor Fiscal Justech"),
            ("latam", "LATAM"),
        ],
        string="Origen",
        required=True,
    )
    consumes_sequence = fields.Boolean(string="Consume secuencia")
    consumes_sequence_label = fields.Char(
        string="Consume secuencia",
        compute="_compute_consumes_label",
    )
    status = fields.Selection(
        selection=[
            ("active", "Activo"),
            ("no_range", "Sin rango"),
            ("no_range_needed", "No requiere rango"),
            ("inactive", "Inactivo"),
            ("draft", "Borrador"),
            ("expired", "Vencido"),
            ("depleted", "Agotado"),
            ("cancelled", "Inactivo"),
        ],
        string="Estado (almacenado)",
    )
    # Alias UX: mismo valor que status tras refresh (badge en lista)
    ux_status = fields.Selection(
        selection=[
            ("active", "Activo"),
            ("inactive", "Inactivo"),
            ("expired", "Vencido"),
            ("depleted", "Agotado"),
            ("draft", "Borrador"),
            ("no_range", "Sin rango"),
            ("no_range_needed", "No requiere rango"),
            ("cancelled", "Inactivo"),
        ],
        string="Estado",
        compute="_compute_ux_status",
        store=True,
        index=True,
    )
    status_label = fields.Char(string="Estado (detalle)")
    availability_label = fields.Char(
        string="Disponibilidad",
        compute="_compute_availability_label",
    )
    active_flag = fields.Boolean(string="Activo")
    range_id = fields.Many2one("justech.do.ncf.range", string="Rango", ondelete="set null")
    emission_config_id = fields.Many2one(
        "justech.do.purchase.emission.config", ondelete="set null"
    )
    document_type_id = fields.Many2one(_DocType, ondelete="set null")
    latam_document_type_id = fields.Many2one(
        "l10n_latam.document.type", ondelete="set null"
    )
    sequence_start = fields.Integer(string="Secuencia inicial")
    sequence_end = fields.Integer(string="Secuencia final")
    next_sequence = fields.Integer(string="Secuencia actual")
    next_ncf = fields.Char(string="Próximo NCF")
    remaining_count = fields.Integer(string="Disponibles")
    date_from = fields.Date(string="Fecha inicio")
    date_to = fields.Date(string="Fecha vencimiento")
    year = fields.Char(
        string="Año",
        compute="_compute_year",
        store=True,
        index=True,
    )
    document_medium = fields.Selection(
        selection=[
            ("physical", "Físico"),
            ("electronic", "Electrónico"),
        ],
        string="Físico / Electrónico",
        index=True,
    )
    journal_names = fields.Char(string="Diario")
    responsible_name = fields.Char(string="Responsable")
    usage_count = fields.Integer(string="Usado en histórico")
    last_used = fields.Datetime(string="Último uso")
    is_electronic_supplier = fields.Boolean(string="Proveedor Electrónico")
    is_received_document = fields.Boolean(
        string="Documento Recibido",
        default=False,
        help="True solo para flujo Compras Recibidas (LATAM).",
    )
    document_category = fields.Char(string="Tipo")
    help_text = fields.Text(string="Descripción")
    action_label = fields.Char(compute="_compute_action_label", string="Acción")
    participates_606 = fields.Boolean(string="606")
    participates_607 = fields.Boolean(string="607")
    participates_608 = fields.Boolean(string="608")
    participates_609 = fields.Boolean(string="609")
    participates_623 = fields.Boolean(string="623")

    @api.depends("company_id", "flow")
    def _compute_company_display(self):
        for rec in self:
            if rec.company_id:
                rec.company_display = rec.company_id.name
            elif rec.flow == "purchase_received":
                rec.company_display = _RECEIVED_COMPANY_LABEL
            else:
                rec.company_display = _RECEIVED_COMPANY_LABEL

    @api.depends("prefix", "name", "flow", "ux_status")
    def _compute_display_name_ux(self):
        flow_labels = dict(self._fields["flow"].selection)
        status_labels = dict(self._fields["ux_status"].selection)
        for rec in self:
            rec.display_name_ux = " — ".join(
                filter(
                    None,
                    [
                        rec.prefix,
                        rec.name,
                        flow_labels.get(rec.flow),
                        status_labels.get(rec.ux_status),
                    ],
                )
            )

    @api.depends("status", "active_flag", "flow")
    def _compute_ux_status(self):
        for rec in self:
            if rec.status:
                rec.ux_status = rec.status
            elif rec.flow == "purchase_received":
                rec.ux_status = "active" if rec.active_flag else "inactive"
            else:
                rec.ux_status = "no_range"

    @api.depends("ux_status", "remaining_count", "consumes_sequence")
    def _compute_availability_label(self):
        for rec in self:
            if not rec.consumes_sequence:
                rec.availability_label = "N/A (recibido)"
            elif rec.ux_status == "active":
                rec.availability_label = "Disponible"
            elif rec.ux_status == "depleted":
                rec.availability_label = "Agotado"
            elif rec.ux_status == "expired":
                rec.availability_label = "Vencido"
            elif rec.ux_status == "draft":
                rec.availability_label = "Borrador"
            else:
                rec.availability_label = "No disponible"

    @api.depends("date_from")
    def _compute_year(self):
        for rec in self:
            rec.year = str(rec.date_from.year) if rec.date_from else False

    @api.depends("consumes_sequence")
    def _compute_consumes_label(self):
        for rec in self:
            rec.consumes_sequence_label = "Sí" if rec.consumes_sequence else "No"

    @api.depends("flow", "range_id", "consumes_sequence", "status")
    def _compute_action_label(self):
        for rec in self:
            if rec.flow == "purchase_received" or not rec.consumes_sequence:
                rec.action_label = "Solo lectura"
            elif rec.range_id:
                rec.action_label = "Administrar rango"
            else:
                rec.action_label = "Configurar rango"

    def action_open_range(self):
        """Abre el rango real en un clic (o el formulario de configuración)."""
        self.ensure_one()
        return self._action_open_range_form(mode="edit")

    def action_view_range(self):
        self.ensure_one()
        return self._action_open_range_form(mode="view")

    def action_edit_range(self):
        self.ensure_one()
        return self._action_open_range_form(mode="edit")

    def action_renew_range(self):
        """Abre el rango activo para renovar vigencia/secuencia (sin inventar datos)."""
        self.ensure_one()
        return self._action_open_range_form(mode="renew")

    def action_view_history(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Histórico — %s") % (self.prefix,),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": {"form_view_initial_mode": "readonly", "justech_focus_history": True},
        }

    def action_view_dgii_validations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Validaciones DGII — %s") % (self.prefix,),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": {"form_view_initial_mode": "readonly", "justech_focus_dgii": True},
        }

    def _center_return_context(self, extra=None):
        ctx = {
            "justech_range_center_id": self.center_id.id,
            "justech_range_center_return": True,
            "default_company_id": self.company_id.id if self.company_id else False,
            "default_document_type_id": self.document_type_id.id
            if self.document_type_id
            else False,
            "default_prefix": self.prefix,
        }
        if extra:
            ctx.update(extra)
        return ctx

    def _action_open_range_form(self, mode="edit"):
        self.ensure_one()
        if self.flow == "purchase_received" or not self.consumes_sequence:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No requiere rango"),
                    "message": _(
                        "Las compras recibidas usan NCF del proveedor "
                        "(configuración LATAM). No hay rango Justech que administrar."
                    ),
                    "type": "info",
                    "sticky": False,
                },
            }
        if self.company_id and self.company_id not in self.env.companies:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Empresa no autorizada"),
                    "message": _(
                        "Active la empresa correspondiente en el selector multiempresa."
                    ),
                    "type": "warning",
                    "sticky": False,
                },
            }

        Range = self.env["justech.do.ncf.range"]
        rng = self.range_id
        if not rng and self.company_id and self.prefix:
            # Re-resolve sin inventar: prefijo + empresa (evita «Sin rango» falso).
            candidates = Range.search(
                [
                    ("company_id", "=", self.company_id.id),
                    ("prefix", "=", self.prefix),
                    ("state", "=", "active"),
                ],
                order="date_to desc, id desc",
            )
            if len(candidates) > 1:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Inconsistencia de rangos"),
                        "message": _(
                            "Hay %(n)s rangos activos para %(prefix)s en %(company)s. "
                            "No se selecciona uno en silencio. Use la lista avanzada."
                        )
                        % {
                            "n": len(candidates),
                            "prefix": self.prefix,
                            "company": self.company_id.display_name,
                        },
                        "type": "warning",
                        "sticky": True,
                    },
                }
            rng = candidates[:1]

        if rng:
            if rng.company_id not in self.env.companies:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Empresa no autorizada"),
                        "message": _(
                            "Active la empresa del rango en el selector multiempresa "
                            "para administrarlo."
                        ),
                        "type": "warning",
                        "sticky": False,
                    },
                }
            title = {
                "view": _("Ver rango"),
                "edit": _("Editar rango"),
                "renew": _("Renovar rango"),
            }.get(mode, _("Administrar rango"))
            return {
                "type": "ir.actions.act_window",
                "name": title,
                "res_model": "justech.do.ncf.range",
                "res_id": rng.id,
                "view_mode": "form",
                "views": [(False, "form")],
                "target": "new",
                "context": self._center_return_context(
                    {
                        "form_view_initial_mode": "readonly"
                        if mode == "view"
                        else "edit",
                        "justech_renew_hint": mode == "renew",
                    }
                ),
            }

        # Configurar: formulario nuevo directo (sin lista intermedia).
        if self.flow in ("sale", "purchase_issued") and self.document_type_id:
            existing = Range.search(
                [
                    ("company_id", "=", self.company_id.id),
                    ("document_type_id", "=", self.document_type_id.id),
                ],
                order="date_to desc, id desc",
                limit=2,
            )
            if not existing:
                existing = Range.search(
                    [
                        ("company_id", "=", self.company_id.id),
                        ("prefix", "=", self.prefix),
                    ],
                    order="date_to desc, id desc",
                    limit=2,
                )
            if len(existing) == 1:
                return {
                    "type": "ir.actions.act_window",
                    "name": _("Configurar rango"),
                    "res_model": "justech.do.ncf.range",
                    "res_id": existing.id,
                    "view_mode": "form",
                    "views": [(False, "form")],
                    "target": "new",
                    "context": self._center_return_context(),
                }
            if len(existing) > 1:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Varios rangos encontrados"),
                        "message": _(
                            "Existen varios rangos para %(prefix)s. "
                            "Abra la lista avanzada para elegir el correcto; "
                            "no se selecciona uno en silencio."
                        )
                        % {"prefix": self.prefix},
                        "type": "warning",
                        "sticky": True,
                    },
                }
            return {
                "type": "ir.actions.act_window",
                "name": _("Configurar rango"),
                "res_model": "justech.do.ncf.range",
                "view_mode": "form",
                "views": [(False, "form")],
                "target": "new",
                "context": self._center_return_context(),
            }
        return True
