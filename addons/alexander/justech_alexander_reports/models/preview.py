from odoo import api, fields, models

DOC_TYPES = [
    ("quotation", "Cotización"),
    ("sale_order", "Orden de Venta"),
    ("invoice", "Factura"),
    ("credit_note", "Nota de Crédito"),
    ("purchase_order", "Orden de Compra"),
    ("rfq", "RFQ"),
    ("delivery", "Conduce / Delivery Slip"),
    ("reception", "Recepción"),
    ("payment_receipt", "Recibo de Pago"),
    ("statement", "Estado de Cuenta"),
    ("warranty", "Certificado de Garantía"),
]


class DoralexReportPreview(models.TransientModel):
    _name = "doralex.report.preview"
    _description = "Vista previa de documentos Doralex"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    doc_type = fields.Selection(DOC_TYPES, required=True, default="quotation")
    preview_note = fields.Char(
        default="Datos de demostración. No consume NCF ni contabiliza.",
        readonly=True,
    )

    def _demo_payload(self):
        self.ensure_one()
        company = self.company_id
        title = dict(DOC_TYPES).get(self.doc_type, "Documento")
        return {
            "company": company,
            "title": title,
            "number": "%s/DEMO/00001" % (company.dx_short_code or "DX"),
            "date": fields.Date.context_today(self),
            "partner_name": "Cliente de demostración",
            "partner_address": "Av. demostración 100, Santo Domingo",
            "lines": [
                {
                    "code": "DEMO-01",
                    "name": "Artículo de ejemplo con descripción suficientemente larga para validar saltos de línea en la tabla A4.",
                    "qty": 3,
                    "uom": "Ud",
                    "price": 1500.0,
                    "subtotal": 4500.0,
                },
                {
                    "code": "DEMO-02",
                    "name": "Servicio de ejemplo",
                    "qty": 1,
                    "uom": "Ud",
                    "price": 2500.0,
                    "subtotal": 2500.0,
                },
            ]
            + [
                {
                    "code": "DEMO-%02d" % idx,
                    "name": "Línea de volumen %s para probar varias páginas y descripciones largas en el layout A4."
                    % idx,
                    "qty": 1,
                    "uom": "Ud",
                    "price": 100.0,
                    "subtotal": 100.0,
                }
                for idx in range(3, 28)
            ],
            "amount_untaxed": 9500.0,
            "amount_tax": 1710.0,
            "amount_total": 11210.0,
            "terms": company.dx_report_terms
            or "Documento de demostración. Condiciones comerciales según acuerdo.",
            "banks": [],
            "show_signature": company.dx_report_show_signature,
            "salesperson": (
                "Equipo comercial" if company.dx_report_show_salesperson else ""
            ),
        }

    def action_print(self):
        self.ensure_one()
        self.env["doralex.admin.auth.service"].require_session()
        return self.env.ref(
            "justech_alexander_reports.action_report_doralex_preview"
        ).report_action(self)

    @api.model
    def action_open(self):
        rec = self.create({})
        return {
            "type": "ir.actions.act_window",
            "name": "Vista previa de documentos",
            "res_model": "doralex.report.preview",
            "res_id": rec.id,
            "view_mode": "form",
            "target": "current",
        }
