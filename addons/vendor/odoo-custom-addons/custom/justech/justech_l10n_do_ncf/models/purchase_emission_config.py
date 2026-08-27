"""Configuración por empresa de emisión B11/B13/B17 desde Compras.

Catálogo normativo = global (justech.do.fiscal.document.type).
Rangos/secuencias = por empresa. Sin rango autorizado ⇒ no emitir.
"""
from odoo import api, fields, models

_DocType = "justech.do.fiscal.document.type"
_PURCHASE_PREFIXES = ("B11", "B13", "B17")


class JustechDoPurchaseEmissionConfig(models.Model):
    _name = "justech.do.purchase.emission.config"
    _description = "Emisión NCF desde Compras (por empresa)"
    _order = "company_id, prefix"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        ondelete="cascade",
    )
    document_type_id = fields.Many2one(
        _DocType,
        string="Tipo de comprobante",
        required=True,
        ondelete="restrict",
        domain="[('is_purchase_document', '=', True)]",
    )
    prefix = fields.Char(related="document_type_id.prefix", store=True, index=True)
    code = fields.Char(related="document_type_id.code", store=True)
    name_full = fields.Char(
        string="Nombre completo",
        compute="_compute_name_full",
        store=True,
    )
    allows_purchase_emission = fields.Boolean(
        string="Permite emisión desde Compras",
        default=True,
        help="Marca normativa: el tipo puede emitirse desde Compras cuando haya rango.",
    )
    range_id = fields.Many2one(
        "justech.do.ncf.range",
        string="Rango asociado",
        compute="_compute_range_state",
    )
    authorization_date = fields.Date(
        string="Fecha de autorización",
        compute="_compute_range_state",
    )
    expiration_date = fields.Date(
        string="Fecha de vencimiento",
        compute="_compute_range_state",
    )
    sequence_start = fields.Integer(compute="_compute_range_state")
    sequence_end = fields.Integer(compute="_compute_range_state")
    next_ncf = fields.Char(
        string="Siguiente NCF",
        compute="_compute_range_state",
    )
    emission_enabled = fields.Boolean(
        string="Emisión habilitada",
        compute="_compute_range_state",
        help="True solo si hay rango Justech activo vigente con números disponibles.",
    )
    status = fields.Selection(
        selection=[
            ("active", "Configurado y activo"),
            ("inactive_range", "Configurado pero inactivo"),
            ("no_range", "Sin rango autorizado"),
            ("expired", "Rango vencido"),
            ("depleted", "Rango agotado"),
        ],
        string="Estado",
        compute="_compute_range_state",
    )
    status_label = fields.Char(string="Estado visible", compute="_compute_range_state")

    _sql_constraints = [
        (
            "company_document_uniq",
            "unique(company_id, document_type_id)",
            "Ya existe configuración de emisión de compras para este tipo y empresa.",
        ),
    ]

    @api.depends("document_type_id", "document_type_id.prefix", "document_type_id.name")
    def _compute_name_full(self):
        names = self.env[_DocType].PURCHASE_DOC_FULL_NAMES
        for rec in self:
            prefix = rec.prefix or ""
            label = names.get(prefix) or (rec.document_type_id.name or "")
            rec.name_full = f"{prefix} — {label}" if prefix else label

    @api.depends(
        "company_id",
        "document_type_id",
        "prefix",
        "allows_purchase_emission",
    )
    def _compute_range_state(self):
        Range = self.env["justech.do.ncf.range"]
        today = fields.Date.context_today(self)
        for rec in self:
            rec.range_id = False
            rec.authorization_date = False
            rec.expiration_date = False
            rec.sequence_start = 0
            rec.sequence_end = 0
            rec.next_ncf = False
            rec.emission_enabled = False
            rec.status = "no_range"
            rec.status_label = "Sin rango autorizado"
            if not rec.company_id or not rec.document_type_id:
                continue
            ranges = Range.search(
                [
                    ("company_id", "=", rec.company_id.id),
                    ("document_type_id", "=", rec.document_type_id.id),
                ],
                order="date_to desc, id desc",
            )
            if not ranges:
                continue
            active = ranges.filtered(lambda r: r.state == "active")[:1]
            rng = active or ranges[:1]
            rec.range_id = rng
            rec.authorization_date = rng.date_from
            rec.expiration_date = rng.date_to
            rec.sequence_start = rng.sequence_start
            rec.sequence_end = rng.sequence_end
            if rng.next_sequence and rng.prefix:
                rec.next_ncf = f"{rng.prefix}{int(rng.next_sequence):08d}"
            if rng.state == "expired" or (rng.date_to and rng.date_to < today):
                rec.status = "expired"
                rec.status_label = "Rango vencido"
            elif rng.state == "depleted" or (
                rng.state == "active"
                and rng.next_sequence
                and rng.next_sequence > rng.sequence_end
            ):
                rec.status = "depleted"
                rec.status_label = "Rango agotado"
            elif rng.state == "active" and rec.allows_purchase_emission:
                rec.status = "active"
                rec.status_label = "Configurado y activo"
                rec.emission_enabled = True
            else:
                rec.status = "inactive_range"
                rec.status_label = "Configurado pero inactivo"

    @api.model
    def ensure_configs_for_companies(self, companies=None):
        """Crea filas de configuración B11/B13/B17 sin inventar rangos."""
        companies = companies or self.env["res.company"].search([])
        DocType = self.env[_DocType]
        created = self.env[self._name]
        for company in companies:
            for prefix in _PURCHASE_PREFIXES:
                doc = DocType.get_by_prefix(prefix, company=company)
                if not doc:
                    continue
                existing = self.search(
                    [
                        ("company_id", "=", company.id),
                        ("document_type_id", "=", doc.id),
                    ],
                    limit=1,
                )
                if existing:
                    continue
                created |= self.create(
                    {
                        "company_id": company.id,
                        "document_type_id": doc.id,
                        "allows_purchase_emission": True,
                    }
                )
        return created

    def is_emission_ready(self):
        self.ensure_one()
        return bool(self.emission_enabled and self.range_id)

    @api.model
    def get_for(self, company, document_type):
        if not company or not document_type:
            return self.browse()
        return self.search(
            [
                ("company_id", "=", company.id),
                ("document_type_id", "=", document_type.id),
            ],
            limit=1,
        )

    def action_open_range(self):
        """Abrir rango asociado o asistente de creación filtrado al tipo/empresa."""
        self.ensure_one()
        if self.range_id:
            return {
                "type": "ir.actions.act_window",
                "name": "Rango NCF",
                "res_model": "justech.do.ncf.range",
                "view_mode": "form",
                "res_id": self.range_id.id,
                "target": "current",
            }
        return {
            "type": "ir.actions.act_window",
            "name": "Configurar rango NCF",
            "res_model": "justech.do.ncf.range",
            "view_mode": "list,form",
            "domain": [
                ("company_id", "=", self.company_id.id),
                ("document_type_id", "=", self.document_type_id.id),
            ],
            "context": {
                "default_company_id": self.company_id.id,
                "default_document_type_id": self.document_type_id.id,
                "default_prefix": self.prefix,
            },
            "target": "current",
        }
