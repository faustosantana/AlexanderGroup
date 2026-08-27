import base64
import csv
import io
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class JustechDoFiscalReport(models.Model):
    _name = "justech.do.fiscal.report"
    _description = "Ejecución de reporte fiscal DGII"
    _order = "date_from desc, id desc"

    DGII_EXPORTER_MODELS = {
        "606": "justech.do.dgii.606.exporter",
        "607": "justech.do.dgii.607.exporter",
        "608": "justech.do.dgii.608.exporter",
        "609": "justech.do.dgii.609.exporter",
        "623": "justech.do.dgii.623.exporter",
    }

    name = fields.Char(string="Nombre", required=True)
    report_type = fields.Selection(
        selection=[
            ("606", "606 — Compras"),
            ("607", "607 — Ventas"),
            ("608", "608 — NCF anulados"),
            ("609", "609 — Pagos exterior"),
            ("623", "623 — Retenciones Estado"),
        ],
        string="Tipo de reporte",
        required=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(string="Desde", required=True)
    date_to = fields.Date(string="Hasta", required=True)
    state = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("done", "Generado"),
        ],
        string="Estado",
        default="draft",
    )
    generated_at = fields.Datetime(string="Fecha de generación", readonly=True)
    generated_by_id = fields.Many2one("res.users", string="Generado por", readonly=True)
    line_ids = fields.One2many(
        "justech.do.fiscal.report.line",
        "report_id",
        string="Líneas",
    )
    line_count = fields.Integer(string="Cantidad de líneas", compute="_compute_totals")
    total_untaxed = fields.Float(
        string="Subtotal gravado",
        compute="_compute_totals",
        digits=(16, 2),
    )
    total_tax = fields.Float(string="Total ITBIS", compute="_compute_totals", digits=(16, 2))
    total_amount = fields.Float(string="Total general", compute="_compute_totals", digits=(16, 2))
    export_file = fields.Binary(string="Archivo exportado", attachment=True)
    export_filename = fields.Char(string="Nombre de archivo")
    validation_log = fields.Text(string="Resultado de validación", readonly=True)
    validation_state = fields.Selection(
        selection=[
            ("pending", "Sin validar"),
            ("ok", "Válido"),
            ("warning", "Con advertencias"),
            ("error", "Sin documentos válidos"),
            ("empty", "Sin movimientos"),
        ],
        string="Estado de validación",
        compute="_compute_validation_state",
        store=True,
        readonly=True,
    )
    count_all = fields.Integer(string="Documentos en período", readonly=True)
    count_valid = fields.Integer(string="Válidos exportados", readonly=True)
    count_incomplete = fields.Integer(string="Incompletos", readonly=True)
    count_excluded = fields.Integer(string="Excluidos", readonly=True)
    count_cancelled = fields.Integer(string="Anulados", readonly=True)
    count_partners_errors = fields.Integer(string="Proveedores con errores", readonly=True)
    error_report_file = fields.Binary(string="Reporte de errores", attachment=True, readonly=True)
    error_report_filename = fields.Char(string="Nombre reporte errores", readonly=True)
    period_code = fields.Char(
        string="Período YYYYMM",
        index=True,
    )
    active = fields.Boolean(string="Activo", default=True, index=True)

    @api.depends("line_ids", "line_ids.amount_untaxed", "line_ids.amount_tax", "line_ids.amount_total")
    def _compute_totals(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.total_untaxed = sum(rec.line_ids.mapped("amount_untaxed"))
            rec.total_tax = sum(rec.line_ids.mapped("amount_tax"))
            rec.total_amount = sum(rec.line_ids.mapped("amount_total"))

    @api.depends(
        "count_all",
        "count_valid",
        "count_incomplete",
        "validation_log",
    )
    def _compute_validation_state(self):
        for rec in self:
            if not rec.validation_log:
                rec.validation_state = "pending"
            elif not rec.count_all:
                rec.validation_state = "empty"
            elif rec.count_valid and rec.count_incomplete:
                rec.validation_state = "warning"
            elif rec.count_valid:
                rec.validation_state = "ok"
            else:
                rec.validation_state = "error"

    def _is_itbis_tax_line(self, line):
        tax = line.tax_line_id
        if not tax:
            return False
        return self.env["justech.do.dgii.tax.classifier"].is_itbis(tax)

    def _move_itbis_amount(self, move):
        return self.env["justech.do.dgii.tax.classifier"].move_itbis_amount(move, "606")

    def _get_dgii_exporter_model(self):
        self.ensure_one()
        return self.DGII_EXPORTER_MODELS.get(self.report_type)

    def _get_dgii_exporter(self):
        self.ensure_one()
        model = self._get_dgii_exporter_model()
        return self.env[model] if model else False

    def _apply_dgii_validation_result(self, result, exporter):
        self.ensure_one()
        counts = result["counts"]
        self.write(
            {
                "validation_log": exporter.format_validation_summary(result),
                "count_all": counts["all"],
                "count_valid": counts["valid"],
                "count_incomplete": counts["incomplete"],
                "count_excluded": counts["excluded"],
                "count_cancelled": counts["cancelled"],
                "count_partners_errors": counts["partners_affected"],
            }
        )
        error_content, error_filename = exporter.export_errors_xlsx(
            self.company_id, self.date_from, self.date_to, result=result
        )
        self.error_report_file = error_content
        self.error_report_filename = error_filename

    def action_validate(self):
        for report in self:
            if not report._get_dgii_exporter_model():
                report.validation_log = _(
                    "Validación detallada no disponible para formato %(type)s."
                ) % {"type": report.report_type}
                continue
            exporter = report._get_dgii_exporter()
            result = exporter.validate_period(
                report.company_id, report.date_from, report.date_to
            )
            report._apply_dgii_validation_result(result, exporter)
        return True

    def action_download_errors(self):
        self.ensure_one()
        if not self.error_report_file:
            self.action_validate()
        if not self.error_report_file:
            raise UserError(_("No hay reporte de errores para descargar."))
        return {
            "type": "ir.actions.act_url",
            "url": (
                f"/web/content/?model=justech.do.fiscal.report&id={self.id}"
                f"&field=error_report_file&filename_field=error_report_filename&download=true"
            ),
            "target": "self",
        }

    def _get_exportable_lines(self):
        """Líneas elegibles para exportación; refinado en revisión fiscal."""
        self.ensure_one()
        return self.line_ids

    def action_export_dgii(self, moves=None):
        self.ensure_one()
        if not self._get_dgii_exporter_model():
            raise UserError(
                _("La exportación DGII oficial no está disponible para el formato %(type)s.")
                % {"type": self.report_type}
            )
        exporter = self._get_dgii_exporter()
        if self.state not in ("done", "generated"):
            if moves is None:
                exportable = self._get_exportable_lines()
                moves = exportable.mapped("move_id") if exportable else None
            self.action_generate(valid_moves=moves)
        if moves is None:
            moves = self._get_exportable_lines().mapped("move_id")
        content, filename = exporter.export_xlsx(
            self.company_id, self.date_from, self.date_to, moves=moves
        )
        self.write(
            {
                "export_file": content,
                "export_filename": filename,
                "count_valid": len(moves),
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": (
                f"/web/content/?model=justech.do.fiscal.report&id={self.id}"
                f"&field=export_file&filename_field=export_filename&download=true"
            ),
            "target": "self",
        }

    def action_export_dgii_606(self, moves=None):
        self.ensure_one()
        if self.report_type != "606":
            raise UserError(_("La exportación DGII oficial solo está disponible para el formato 606."))
        return self.action_export_dgii(moves=moves)

    def action_export_dgii_607(self, moves=None):
        self.ensure_one()
        if self.report_type != "607":
            raise UserError(_("La exportación DGII oficial solo está disponible para el formato 607."))
        return self.action_export_dgii(moves=moves)

    def action_export_dgii_608(self, moves=None):
        self.ensure_one()
        if self.report_type != "608":
            raise UserError(_("La exportación DGII oficial solo está disponible para el formato 608."))
        return self.action_export_dgii(moves=moves)

    def action_export_dgii_609(self, moves=None):
        self.ensure_one()
        if self.report_type != "609":
            raise UserError(_("La exportación DGII oficial solo está disponible para el formato 609."))
        return self.action_export_dgii(moves=moves)

    def action_export_dgii_623(self, moves=None):
        self.ensure_one()
        if self.report_type != "623":
            raise UserError(_("La exportación DGII oficial solo está disponible para el formato 623."))
        return self.action_export_dgii(moves=moves)

    def action_generate(self, valid_moves=None):
        for report in self:
            report.line_ids.unlink()
            lines = report._collect_lines(valid_moves=valid_moves)
            report.write(
                {
                    "line_ids": [(0, 0, line) for line in lines],
                    "state": "done",
                    "generated_at": fields.Datetime.now(),
                    "generated_by_id": self.env.user.id,
                }
            )
        return True

    def _collect_lines(self, valid_moves=None):
        self.ensure_one()
        if self.report_type == "606":
            return self._lines_606(valid_moves=valid_moves)
        if self.report_type == "607":
            return self._lines_607(valid_moves=valid_moves)
        if self.report_type == "608":
            return self._lines_608(valid_moves=valid_moves)
        if self.report_type == "609":
            return self._lines_609(valid_moves=valid_moves)
        if self.report_type == "623":
            return self._lines_623(valid_moves=valid_moves)
        return []

    def _base_move_domain(self):
        return [
            ("company_id", "=", self.company_id.id),
            ("state", "=", "posted"),
            ("invoice_date", ">=", self.date_from),
            ("invoice_date", "<=", self.date_to),
        ]

    def _lines_606(self, valid_moves=None):
        fdp = self.env["justech.do.fiscal.data.provider"]
        if valid_moves is not None:
            moves = valid_moves
        else:
            exporter = self.env["justech.do.dgii.606.exporter"]
            moves = exporter._moves_for_period(
                self.company_id, self.date_from, self.date_to, only_valid=True
            )
        lines = []
        for move in moves:
            itbis = self._move_itbis_amount(move)
            lines.append(
                {
                    "partner_vat": move.partner_id.vat or "",
                    "partner_name": move.partner_id.name,
                    "ncf": fdp.get_ncf(move) or "",
                    "document_date": move.invoice_date,
                    "amount_untaxed": abs(move.amount_untaxed_signed),
                    "amount_tax": itbis,
                    "amount_total": abs(move.amount_total_signed),
                    "move_id": move.id,
                }
            )
        return lines

    def _lines_607(self, valid_moves=None):
        fdp = self.env["justech.do.fiscal.data.provider"]
        if valid_moves is not None:
            moves = valid_moves
        else:
            exporter = self.env["justech.do.dgii.607.exporter"]
            moves = exporter._moves_for_period(
                self.company_id, self.date_from, self.date_to, only_valid=True
            )
        lines = []
        for move in moves:
            itbis = self._move_itbis_amount(move)
            lines.append(
                {
                    "partner_vat": move.partner_id.vat or "",
                    "partner_name": move.partner_id.name,
                    "ncf": fdp.get_ncf(move),
                    "document_type": fdp.get_document_type_prefix(move),
                    "document_date": move.invoice_date,
                    "amount_untaxed": abs(move.amount_untaxed_signed),
                    "amount_tax": itbis,
                    "amount_total": abs(move.amount_total_signed),
                    "move_id": move.id,
                }
            )
        return lines

    def _lines_608(self, valid_moves=None):
        fdp = self.env["justech.do.fiscal.data.provider"]
        if valid_moves is not None:
            moves = valid_moves
        else:
            exporter = self.env["justech.do.dgii.608.exporter"]
            moves = exporter._moves_for_period(
                self.company_id, self.date_from, self.date_to, only_valid=True
            )
        lines = []
        for move in moves.filtered(lambda m: fdp.get_ncf(m)):
            void_meta = fdp.get_void_metadata(move)
            lines.append(
                {
                    "partner_vat": move.partner_id.vat or "",
                    "partner_name": move.partner_id.name,
                    "ncf": void_meta["ncf"],
                    "document_type": fdp.get_document_type_prefix(move),
                    "document_date": move.invoice_date or void_meta["void_date"],
                    "notes": void_meta["void_reason"] or "",
                    "move_id": move.id,
                }
            )
        return lines

    def _lines_609(self, valid_moves=None):
        fdp = self.env["justech.do.fiscal.data.provider"]
        if valid_moves is not None:
            moves = valid_moves
        else:
            exporter = self.env["justech.do.dgii.609.exporter"]
            moves = exporter._moves_for_period(
                self.company_id, self.date_from, self.date_to, only_valid=True
            )
        lines = []
        for move in moves:
            lines.append(
                {
                    "partner_vat": move.partner_id.vat or "",
                    "partner_name": move.partner_id.name,
                    "ncf": fdp.get_foreign_document_ref(move),
                    "document_type": fdp.get_foreign_service_type(move),
                    "document_date": move.invoice_date,
                    "amount_untaxed": abs(move.amount_untaxed_signed),
                    "amount_tax": 0.0,
                    "amount_total": abs(move.amount_total_signed),
                    "notes": move.partner_id.country_id.code or "",
                    "move_id": move.id,
                }
            )
        return lines

    def _lines_623(self, valid_moves=None):
        fdp = self.env["justech.do.fiscal.data.provider"]
        if valid_moves is not None:
            moves = valid_moves
        else:
            exporter = self.env["justech.do.dgii.623.exporter"]
            moves = exporter._moves_for_period(
                self.company_id, self.date_from, self.date_to, only_valid=True
            )
        exporter = self.env["justech.do.dgii.623.exporter"]
        gov_tax = exporter._gov_tax(self.company_id)
        lines = []
        for move in moves:
            gov_amt = exporter._gov_amount(move, gov_tax)
            lines.append(
                {
                    "partner_vat": move.partner_id.vat or "",
                    "partner_name": move.partner_id.name,
                    "ncf": fdp.get_ncf(move) or move.name,
                    "document_type": "5% Gobierno",
                    "document_date": exporter._retention_date(move),
                    "amount_untaxed": abs(move.amount_untaxed_signed),
                    "amount_tax": gov_amt,
                    "amount_total": gov_amt,
                    "notes": fdp.get_payment_reference(move),
                    "move_id": move.id,
                }
            )
        return lines

    def action_export_csv(self):
        self.ensure_one()
        output = io.StringIO()
        if self.report_type == "606":
            fields_list = [
                "partner_vat",
                "partner_name",
                "ncf",
                "document_date",
                "amount_untaxed",
                "amount_tax",
                "amount_total",
            ]
            headers = {
                "partner_vat": "RNC",
                "partner_name": "Proveedor",
                "ncf": "NCF",
                "document_date": "Fecha",
                "amount_untaxed": "Monto gravado",
                "amount_tax": "ITBIS",
                "amount_total": "Total",
            }
        elif self.report_type == "607":
            fields_list = [
                "partner_vat",
                "partner_name",
                "ncf",
                "document_type",
                "document_date",
                "amount_untaxed",
                "amount_tax",
                "amount_total",
            ]
            headers = {
                "partner_vat": "RNC",
                "partner_name": "Cliente",
                "ncf": "NCF",
                "document_type": "Tipo",
                "document_date": "Fecha",
                "amount_untaxed": "Monto gravado",
                "amount_tax": "ITBIS",
                "amount_total": "Total",
            }
        else:
            fields_list = [
                "ncf",
                "partner_vat",
                "partner_name",
                "document_date",
                "notes",
            ]
            headers = {
                "ncf": "NCF",
                "partner_vat": "RNC",
                "partner_name": "Contacto",
                "document_date": "Fecha anulación",
                "notes": "Motivo",
            }
        writer = csv.DictWriter(
            output,
            fieldnames=[headers[f] for f in fields_list],
            extrasaction="ignore",
        )
        writer.writeheader()
        for line in self.line_ids:
            row = {}
            for field_name in fields_list:
                val = line[field_name]
                if isinstance(val, date):
                    val = val.isoformat()
                row[headers[field_name]] = val or ""
            writer.writerow(row)
        content = output.getvalue().encode("utf-8")
        filename = f"DGII_{self.report_type}_{self.date_from}_{self.date_to}.csv"
        self.write(
            {
                "export_file": base64.b64encode(content),
                "export_filename": filename,
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/?model=justech.do.fiscal.report&id={self.id}&field=export_file&filename_field=export_filename&download=true",
            "target": "self",
        }

    def action_export_xlsx(self):
        self.ensure_one()
        try:
            import xlsxwriter
        except ImportError:
            return self.action_export_csv()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet(self.report_type)
        title_fmt = workbook.add_format({"bold": True})
        if self.report_type == "607":
            headers = [
                "RNC",
                "Cliente",
                "NCF",
                "Tipo",
                "Fecha",
                "Monto gravado",
                "ITBIS",
                "Total",
            ]
            row_fields = [
                "partner_vat",
                "partner_name",
                "ncf",
                "document_type",
                "document_date",
                "amount_untaxed",
                "amount_tax",
                "amount_total",
            ]
        elif self.report_type == "606":
            headers = ["RNC", "Proveedor", "NCF", "Fecha", "Monto gravado", "ITBIS", "Total"]
            row_fields = [
                "partner_vat",
                "partner_name",
                "ncf",
                "document_date",
                "amount_untaxed",
                "amount_tax",
                "amount_total",
            ]
        else:
            headers = ["NCF", "RNC", "Contacto", "Fecha anulación", "Motivo"]
            row_fields = [
                "ncf",
                "partner_vat",
                "partner_name",
                "document_date",
                "notes",
            ]
        meta = [
            (_("Compañía"), self.company_id.name),
            (_("Período"), f"{self.date_from} — {self.date_to}"),
            (_("Generado"), self.generated_at and self.generated_at.strftime("%Y-%m-%d %H:%M") or ""),
            (_("Usuario"), self.generated_by_id.name or ""),
            (_("Líneas"), self.line_count),
            (_("Subtotal gravado"), self.total_untaxed),
            (_("Total ITBIS"), self.total_tax),
            (_("Total general"), self.total_amount),
        ]
        row = 0
        for label, value in meta:
            sheet.write(row, 0, label, title_fmt)
            sheet.write(row, 1, value)
            row += 1
        row += 1
        for col, header in enumerate(headers):
            sheet.write(row, col, header, title_fmt)
        for row_idx, line in enumerate(self.line_ids, start=row + 1):
            for col_idx, field_name in enumerate(row_fields):
                val = line[field_name]
                if isinstance(val, date):
                    val = val.isoformat()
                sheet.write(row_idx, col_idx, val or "")
        workbook.close()
        content = output.getvalue()
        filename = f"DGII_{self.report_type}_{self.date_from}_{self.date_to}.xlsx"
        self.write(
            {
                "export_file": base64.b64encode(content),
                "export_filename": filename,
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/?model=justech.do.fiscal.report&id={self.id}&field=export_file&filename_field=export_filename&download=true",
            "target": "self",
        }


class JustechDoFiscalReportLine(models.Model):
    _name = "justech.do.fiscal.report.line"
    _description = "Línea de reporte fiscal DGII"

    report_id = fields.Many2one(
        "justech.do.fiscal.report",
        string="Reporte",
        required=True,
        ondelete="cascade",
    )
    partner_vat = fields.Char(string="RNC")
    partner_name = fields.Char(string="Nombre")
    ncf = fields.Char(string="NCF")
    document_type = fields.Char(string="Tipo comprobante fiscal")
    document_date = fields.Date(string="Fecha")
    amount_untaxed = fields.Float(string="Monto gravado", digits=(16, 2))
    amount_tax = fields.Float(string="ITBIS", digits=(16, 2))
    amount_total = fields.Float(string="Total", digits=(16, 2))
    notes = fields.Text(string="Notas")
    move_id = fields.Many2one("account.move", string="Asiento", index=True)
