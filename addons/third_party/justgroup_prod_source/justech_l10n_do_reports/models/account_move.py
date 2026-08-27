"""Campos configurables DGII 609 / 607 — pagos al exterior e ingresos."""
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    justech_do_income_type_607 = fields.Selection(
        selection=[
            ("01", "01 — Ingresos por operaciones (no financieros)"),
            ("02", "02 — Ingresos financieros"),
            ("03", "03 — Ingresos extraordinarios"),
            ("04", "04 — Ingresos por arrendamientos"),
            ("05", "05 — Ingresos por venta de activo depreciable"),
            ("06", "06 — Otros ingresos"),
        ],
        string="Tipo de ingreso (607)",
        compute="_compute_justech_do_income_type_607",
        store=True,
        readonly=False,
        copy=False,
        help="Clasificación DGII columna F del formato 607.",
    )

    @api.depends(
        "justech_do_document_type_id",
        "justech_do_document_type_id.prefix",
        "justech_do_ncf",
    )
    def _compute_justech_do_income_type_607(self):
        provider = self.env["justech.do.fiscal.data.provider"]
        for move in self:
            move.justech_do_income_type_607 = provider.get_income_type_607(move)

    justech_do_foreign_609 = fields.Boolean(
        string="Reportar en 609",
        copy=False,
        help="Incluir este documento en el formato 609 aunque el proveedor no tenga país extranjero.",
    )
    justech_do_foreign_service_type = fields.Selection(
        selection=[
            ("01", "Alquileres"),
            ("02", "Honorarios por servicios técnicos"),
            ("03", "Regalías"),
            ("04", "Dividendos"),
            ("05", "Intereses"),
            ("06", "Servicios de transporte"),
            ("07", "Publicidad"),
            ("08", "Telecomunicaciones"),
            ("09", "Otros servicios"),
        ],
        string="Tipo servicio exterior (609)",
        copy=False,
    )
    justech_do_foreign_document_ref = fields.Char(
        string="NCF / documento exterior (609)",
        copy=False,
        help="Número de comprobante o documento que sustenta el pago al exterior.",
    )
    justech_do_foreign_payment_date = fields.Date(
        string="Fecha pago/retención exterior (609)",
        copy=False,
    )
    justech_do_foreign_exchange_rate = fields.Float(
        string="Tasa de cambio (609)",
        digits=(16, 6),
        copy=False,
    )
    justech_do_foreign_presumed_income = fields.Float(
        string="Renta presunta (609)",
        digits=(16, 2),
        copy=False,
    )
    justech_do_foreign_isr_retained = fields.Float(
        string="ISR retenido exterior (609)",
        digits=(16, 2),
        copy=False,
    )
