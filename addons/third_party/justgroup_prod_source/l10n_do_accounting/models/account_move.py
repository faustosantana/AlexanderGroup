# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError
import logging
from .ncf_validate import is_valid

_logger = logging.getLogger(__name__)

ncf_dict = {
    "B01": "fiscal",
    "B02": "consumo",
    "B15": "gov",
    "B14": "especial",
    "B12": "unico",
    "B16": "export",
    "B03": "debit",
    "B04": "credit",
    "B13": "minor",
    "B11": "informal",
    "B17": "exterior",
    "E31": "e-fiscal",
    "E32": "e-consumer",
    "E33": "e-debit_note",
    "E34": "e-credit_note",
    "E41": "e-informal",
    "E43": "e-minor",
    "E44": "e-special",
    "E45": "e-governmental",
    "E46": "e-export",
    "E47": "e-exterior",
}

DESCRIPTION_DEBIT_CODE = [
    ("2", _("02 - Text Correction")),
    ("3", _("03 - Amount correction")),
    ("4", _("04 - NCF replacement issued in contingency")),
    ("5", _("05 - Reference Electronic Consumer Invoice")),
]


class AccountMove(models.Model):
    _inherit = "account.move"

    @property
    def _sequence_fixed_regex(self):
        if self.l10n_latam_country_code == "DO" and self.l10n_latam_use_documents:
            return r'^(?P<prefix1>.*?)(?P<seq>\d{0,9})(?P<suffix>\D*?)$'
        return super(AccountMove, self)._sequence_fixed_regex

    def _get_l10n_do_cancellation_type(self):
        """ Return the list of cancellation types required by DGII. """
        return [
            ("01", _("01 - Pre-printed Invoice Impairment")),
            ("02", _("02 - Printing Errors (Pre-printed Invoice)")),
            ("03", _("03 - Defective Printing")),
            ("04", _("04 - Correction of Product Information")),
            ("05", _("05 - Product Change")),
            ("06", _("06 - Product Return")),
            ("07", _("07 - Product Omission")),
            ("08", _("08 - NCF Sequence Errors")),
            ("09", _("09 - For Cessation of Operations")),
            ("10", _("10 - Lossing or Hurting Of Counterfoil")),
        ]

    def _get_l10n_do_ecf_modification_code(self):
        """ Return the list of e-CF modification codes required by DGII. """
        return [
            ("1", _("01 - Total Cancellation")),
            ("2", _("02 - Text Correction")),
            ("3", _("03 - Amount correction")),
            ("4", _("04 - NCF replacement issued in contingency")),
            ("5", _("05 - Reference Electronic Consumer Invoice")),
        ]

    def _get_l10n_do_income_type(self):
        """ Return the list of income types required by DGII. """
        return [
            ("01", _("01 - Operational Incomes")),
            ("02", _("02 - Financial Incomes")),
            ("03", _("03 - Extraordinary Incomes")),
            ("04", _("04 - Leasing Incomes")),
            ("05", _("05 - Income for Selling Depreciable Assets")),
            ("06", _("06 - Other Incomes")),
        ]

    l10n_do_expense_type = fields.Selection(
        selection=lambda self: self.env["res.partner"]._get_l10n_do_expense_type(),
        string="Cost & Expense Type",
    )
    l10n_do_cancellation_type = fields.Selection(
        selection="_get_l10n_do_cancellation_type",
        string="Cancellation Type",
        copy=False,
    )
    l10n_do_income_type = fields.Selection(
        selection="_get_l10n_do_income_type",
        string="Income Type",
        copy=False,
        default=lambda self: self._context.get("l10n_do_income_type", "01"),
    )
    l10n_do_origin_ncf = fields.Char(
        string="Modifies",
    )
    is_ecf_invoice = fields.Boolean(
        copy=False,
        default=lambda self: self.env.user.company_id.l10n_do_ecf_issuer
                             and self.env.user.company_id.l10n_do_country_code
                             and self.env.user.company_id.l10n_do_country_code == "DO",
    )
    l10n_do_ecf_modification_code = fields.Selection(
        selection="_get_l10n_do_ecf_modification_code",
        string="e-CF Modification Code",
        copy=False,
        readonly=False,
    )
    l10n_do_company_in_contingency = fields.Boolean(
        string="Company in contingency",
        compute="_compute_company_in_contingency",
    )
    l10n_latam_country_code = fields.Char(
        "Country Code",
        related="company_id.country_id.code",
    )
    l10n_do_fiscal_sequence_id = fields.Many2one(
        "account.fiscal.sequence", string="Fiscal Sequence",
        copy=False, compute="_compute_l10n_do_fiscal_sequence", store=True,
    )
    l10n_do_ncf_expiration_date = fields.Date(
        string="Valid until",
    )
    l10n_do_fiscal_sequence_status = fields.Selection(
        [
            ("no_fiscal", "No fiscal"),
            ("fiscal_ok", "Ok"),
            ("almost_no_sequence", "Almost no sequence"),
            ("no_sequence", "Depleted"),
        ],
        compute="_compute_l10n_do_fiscal_sequence_status",
    )
    l10n_latam_amount_untaxed = fields.Monetary(compute='_compute_l10n_latam_amount_and_taxes')
    l10n_latam_tax_ids = fields.One2many(compute="_compute_l10n_latam_amount_and_taxes",
                                         comodel_name='account.move.line')
    l10n_latam_available_document_type_ids = fields.Many2many('l10n_latam.document.type',
                                                              compute='_compute_l10n_latam_available_document_types')
    l10n_latam_document_type_id = fields.Many2one(
        'l10n_latam.document.type', string='Document Type', readonly=False, auto_join=True, index=True,
        compute='_compute_l10n_latam_document_type', store=True)
    l10n_latam_document_number = fields.Char(string='Document Number', copy=False, readonly=False)
    l10n_latam_use_documents = fields.Boolean(related='journal_id.l10n_latam_use_documents')
    l10n_latam_manual_document_number = fields.Boolean(compute='_compute_l10n_latam_manual_document_number',
                                                       string='Manual Number')
    amount_discount = fields.Monetary(store=True, readonly=True, compute='_compute_amount',
                                      tracking=True)
    warning_message = fields.Char(compute='_compute_warning_message', store=True, readonly=True)
    currency_rate = fields.Float(string="Tipo de cambio", compute='_compute_currency_rate')

    @api.depends('l10n_do_fiscal_sequence_id')
    def _compute_warning_message(self):
        for move in self.filtered(lambda m: m.l10n_latam_country_code == "DO" and m.l10n_do_fiscal_sequence_id):
            move.warning_message = False
            warnings = []
            if move.l10n_do_fiscal_sequence_id.warning_gap >= move.l10n_do_fiscal_sequence_id.sequence_remaining:
                warnings.append(
                    "Secuencia fiscal {} proxima a alcanzar el maximo.".format(move.l10n_do_fiscal_sequence_id.name))
            if warnings:
                warnings = [_("This invoice can be erroneous :")] + warnings
                move.warning_message = "\n  ・ ".join(warnings)

    def _compute_currency_rate(self):
        for record in self:
            record.currency_rate = abs(
                round(1 / (self.amount_total / (self.amount_total_signed or 1) or 1), 2)
            )

    def _compute_amount(self):
        super()._compute_amount()
        for inv in self:
            if inv.is_invoice(include_receipts=False) and inv.l10n_latam_country_code == "DO":
                line_total_discount = sum(
                    (line.quantity * line.price_unit - line.price_subtotal) for line in inv.invoice_line_ids)
                discount_global = sum(line.price_unit for line in inv.invoice_line_ids if line.price_unit < 0)
                total_discount = line_total_discount + abs(discount_global)
                inv.amount_discount = total_discount

    @api.depends("company_id", "company_id.l10n_do_ecf_issuer")
    def _compute_company_in_contingency(self):
        for invoice in self:
            ecf_invoices = self.search([("is_ecf_invoice", "=", True)], limit=1)
            invoice.l10n_do_company_in_contingency = bool(
                ecf_invoices and not invoice.company_id.l10n_do_ecf_issuer
            )

    def button_cancel(self):
        fiscal_invoice = self.filtered(
            lambda inv: inv.l10n_latam_country_code == "DO"
                        and self.move_type[-6:] in ("nvoice", "refund")
                        and inv.l10n_latam_use_documents
        )

        if len(fiscal_invoice) > 1:
            raise ValidationError(
                _("You cannot cancel multiple fiscal invoices at a time.")
            )

        if fiscal_invoice and not self.env.user.has_group(
            "l10n_do_accounting.group_l10n_do_fiscal_invoice_cancel"
        ):
            raise AccessError(_("You are not allowed to cancel Fiscal Invoices"))

        if fiscal_invoice:
            action = self.env.ref(
                "l10n_do_accounting.action_account_move_cancel"
            ).read()[0]
            action["context"] = {"default_move_id": fiscal_invoice.id}
            return action

        return super(AccountMove, self).button_cancel()

    def action_reverse(self):
        fiscal_invoice = self.filtered(
            lambda inv: inv.l10n_latam_country_code == "DO"
                        and self.move_type[-6:] in ("nvoice", "refund")
        )
        if fiscal_invoice and not self.env.user.has_group(
                "l10n_do_accounting.group_l10n_do_fiscal_credit_note"
        ):
            raise AccessError(_("You are not allowed to issue Fiscal Credit Notes"))

        return super(AccountMove, self).action_reverse()

    def _get_l10n_latam_documents_domain(self):
        for p in self:
            if not p.partner_id.l10n_do_dgii_tax_payer_type:
                raise ValidationError(
                    _(
                        "A Type Of Taxpayers is Mandatory. "
                        "Please set the current Type of this contact"
                    )
                )

        self.ensure_one()

        if self.move_type in ['out_refund', 'in_refund']:
            internal_types = ['credit_note']
        else:
            internal_types = ['invoice', 'debit_note']
        domain = [('internal_type', 'in', internal_types)]

        if (
            self.journal_id.l10n_latam_use_documents
            and self.journal_id.company_id.country_id == self.env.ref("base.do")
        ):
            if self.partner_id == self.company_id.partner_id and self.move_type not in ['out_refund', 'in_refund']:
                ncf_types = ['minor', 'e-minor', 'import']
            else:
                ncf_types = self.journal_id._get_journal_ncf_types(
                    counterpart_partner=self.partner_id.commercial_partner_id, invoice=self
                )

            domain += [
                "|",
                ("l10n_do_ncf_type", "=", False),
                ("l10n_do_ncf_type", "in", ncf_types),
            ]
            codes = self.journal_id._get_journal_codes()
            if codes:
                domain.append(("code", "in", codes))
        return domain

    @api.constrains("move_type", "l10n_latam_document_type_id")
    def _check_invoice_type_document_type(self):
        # for rec in self.filtered('l10n_latam_document_type_id.internal_type'):
        #     internal_type = rec.l10n_latam_document_type_id.internal_type
        #     invoice_type = rec.move_type
        #     if internal_type in ['debit_note', 'invoice'] and invoice_type in ['out_refund', 'in_refund'] and \
        #             rec.l10n_latam_document_type_id.code != '99':
        #         raise ValidationError(_('You can not use a %s document type with a refund invoice', internal_type))
        #     elif internal_type == 'credit_note' and invoice_type in ['out_invoice', 'in_invoice']:
        #         raise ValidationError(_('You can not use a %s document type with a invoice', internal_type))

        for rec in self.filtered(
                lambda r: r.company_id.country_id == self.env.ref("base.do")
                          and r.l10n_latam_document_type_id
        ):
            partner_vat = rec.partner_id.vat
            l10n_latam_document_type = rec.l10n_latam_document_type_id
            if not partner_vat and l10n_latam_document_type.is_vat_required and rec.move_type not in (
                    'out_refund', 'in_refund'):
                raise ValidationError(
                    _(
                        "A VAT is mandatory for this type of NCF. "
                        "Please set the current VAT of this client"
                    )
                )

            elif rec.move_type in ("out_invoice", "out_refund"):
                if (
                    rec.amount_untaxed_signed >= 250000
                    and l10n_latam_document_type.l10n_do_ncf_type[-7:] != "special"
                    and not rec.partner_id.vat
                ):
                    raise UserError(
                        _(
                            "If the invoice amount is greater than RD$250,000.00 "
                            "the customer should have a VAT to validate the invoice"
                        )
                    )

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if (
                self.company_id.country_id == self.env.ref("base.do")
                and self.l10n_latam_document_type_id
                and self.move_type == "in_invoice"
                and self.partner_id
        ):
            self.l10n_do_expense_type = (
                self.partner_id.l10n_do_expense_type
                if not self.l10n_do_expense_type
                else self.l10n_do_expense_type
            )

        return super(AccountMove, self)._onchange_partner_id()
    

    @api.onchange("l10n_latam_document_number", "l10n_latam_document_type_id")
    def _onchange_l10n_latam_document_number(self):
        """Validación solo estructural en el cambio del NCF."""
        for rec in self:
            rec._validate_ncf(avoid_duplicate_check=True)

    @api.constrains("l10n_latam_document_number", "l10n_latam_document_type_id", "partner_id")
    def _check_l10n_latam_document_number(self):
        """Validación completa, incluyendo la verificación de duplicados."""
        self._validate_ncf()

    def _validate_ncf(self, avoid_duplicate_check=False):
        """Método central de validación de NCF."""
        for rec in self.filtered(
            lambda r: r.company_id.country_id == self.env.ref("base.do")
            and r.l10n_latam_document_type_id.l10n_do_ncf_type
            and r.journal_id.l10n_latam_use_documents
            and r.l10n_latam_document_number
            and r.move_type == "in_invoice"
        ):
            NCF = rec.l10n_latam_document_number or ""
            prefix = NCF[:3] if len(NCF) >= 3 else ""

            # Validación estructural del NCF
            if not is_valid(NCF):
                raise ValidationError(_(
                    "NCF mal digitado\n\n"
                    "El comprobante *{}* no tiene la estructura correcta. "
                    "Por favor, valide si lo ha digitado correctamente."
                ).format(NCF))

            # Validación del prefijo del NCF
            expected_prefix = next((k for k, v in ncf_dict.items() if v == rec.l10n_latam_document_type_id.l10n_do_ncf_type), None)
            if expected_prefix and not NCF.startswith(expected_prefix):
                raise ValidationError(_(
                    "El NCF *{}* no corresponde con el tipo de documento *{}*.\n"
                    "Debe tener el prefijo *{}*.".format(NCF, ncf_dict.get(expected_prefix, "desconocido"), expected_prefix)
                ))

            # Verificación específica de la longitud del NCF
            if prefix.startswith("B") and len(NCF) != 11:
                raise ValidationError(_(
                    "El NCF *{}* debe tener 11 caracteres para prefijos tipo B.".format(NCF)
                ))
            elif prefix.startswith("E") and len(NCF) != 13:
                raise ValidationError(_(
                    "El NCF *{}* debe tener 13 caracteres para prefijos tipo E.".format(NCF)
                ))

            # Verificación de duplicados solo durante la validación completa (no en onchange)
            if not avoid_duplicate_check:
                existing_invoice = self.env['account.move'].search([
                    ('id', '!=', rec.id),
                    ('partner_id', '=', rec.partner_id.id),
                    ('l10n_latam_document_number', '=', rec.l10n_latam_document_number),
                    ('l10n_latam_document_type_id', '=', rec.l10n_latam_document_type_id.id),
                    ('move_type', '=', 'in_invoice'),
                    ('state', '!=', 'cancel')
                ], limit=1)
                
                if existing_invoice:
                    raise ValidationError(_(
                        "El NCF *{}* ya está registrado en la factura *{}* para el proveedor *{}*.\n"
                        "No puede crear múltiples facturas con el mismo NCF para el mismo proveedor y tipo de documento."
                    ).format(NCF, existing_invoice.name, rec.partner_id.name))


    @api.constrains("name", "partner_id", "company_id")
    def _check_unique_vendor_number(self):
        l10n_do_invoice = self.filtered(
            lambda inv: inv.l10n_latam_country_code == "DO"
                        and inv.l10n_latam_use_documents
                        and inv.is_purchase_document()
                        and inv.l10n_latam_document_number
        )

        for rec in l10n_do_invoice:
            domain = [
                ("move_type", "=", rec.move_type),
                ("l10n_latam_document_number", "=", rec.l10n_latam_document_number),
                ("company_id", "=", rec.company_id.id),
                ("id", "!=", rec.id),
                ("commercial_partner_id", "=", rec.commercial_partner_id.id),
            ]
            if rec.search(domain):
                raise ValidationError(
                    _("Vendor bill NCF must be unique per vendor and company.")
                )

    def _is_manual_document_number(self):
        if (
            self.company_id.country_id == self.env.ref("base.do")
            and self.l10n_latam_document_type_id
        ):
            return self.move_type in (
                "in_invoice",
                "in_refund",
            ) and self.l10n_latam_document_type_id.l10n_do_ncf_type not in (
                "minor",
                "e-minor",
                "informal",
                "e-informal",
                "exterior",
                "e-exterior",
            )

    # def _get_name_invoice_report(self):
    #     self.ensure_one()
    #     # if self.l10n_latam_use_documents and self.l10n_latam_country_code == "DO":
    #     #     return "l10n_do_accounting.report_invoice_document_inherited"
    #     # return super()._get_name_invoice_report()
    #     return "l10n_do_accounting.report_invoice_document_inherited"

    @api.depends(
        "journal_id",
        "l10n_latam_use_documents",
        "state",
        "l10n_latam_document_type_id",
        "invoice_date", "move_type",
    )
    def _compute_l10n_do_fiscal_sequence(self):
        """ Compute the sequence and fiscal position to be used depending on
            the fiscal type that has been set on the invoice (or partner).
        """
        for inv in self:
            assing_document_number = False
            if (
                inv.move_type in ("out_invoice", "out_refund", "in_refund")
                # inv.move_type in ("out_invoice", "out_refund")
            ):
                assing_document_number = True

            if (
                inv.move_type == "in_invoice"
                and inv.l10n_latam_document_type_id.l10n_do_ncf_type in ("minor", "e-minor")
                and inv.partner_id == inv.company_id.partner_id
            ):
                assing_document_number = True

            if (
                inv.move_type == "in_invoice"
                and inv.l10n_latam_document_type_id.l10n_do_ncf_type in ("informal", "e-informal")
                and inv.partner_id.vat and len(inv.partner_id.vat) == 11
            ):
                assing_document_number = True

            if (
                inv.move_type == "in_invoice"
                and inv.l10n_latam_document_type_id.l10n_do_ncf_type in ("exterior", "e-exterior")
            ):
                assing_document_number = True

            if inv.l10n_latam_use_documents and assing_document_number:

                domain = [
                    ('company_id', 'parent_of', inv.company_id.ids),
                    ("fiscal_type_id", "=", inv.l10n_latam_document_type_id.id),
                    ("state", "=", "active"),
                ]
                if inv.invoice_date:
                    domain.append(("expiration_date", ">=", inv.invoice_date))
                else:
                    today = fields.Date.context_today(inv)
                    domain.append(("expiration_date", ">=", today))

                l10n_do_fiscal_sequence_id = inv.env["account.fiscal.sequence"].search(
                    domain, order="expiration_date, id desc"
                )

                if not l10n_do_fiscal_sequence_id:
                    continue

                l10n_do_fiscal_sequence_id.ensure_one()

                if l10n_do_fiscal_sequence_id.state == "active":
                    inv.l10n_do_fiscal_sequence_id = l10n_do_fiscal_sequence_id
                else:
                    inv.l10n_do_fiscal_sequence_id = False
            else:
                inv.l10n_do_fiscal_sequence_id = False

    @api.depends(
        "l10n_do_fiscal_sequence_id",
        "l10n_do_fiscal_sequence_id.sequence_remaining",
        "l10n_do_fiscal_sequence_id.remaining_percentage",
        "state",
        "journal_id",
    )
    def _compute_l10n_do_fiscal_sequence_status(self):
        """ Identify the percentage fiscal sequences that has been used so far.
            With this result the user can be warned if it's above the threshold
            or if there's no more sequences available.
        """
        for inv in self:
            if not inv.l10n_latam_use_documents or not inv.l10n_do_fiscal_sequence_id:
                inv.l10n_do_fiscal_sequence_status = "no_fiscal"
            else:
                fs_id = inv.l10n_do_fiscal_sequence_id  # Fiscal Sequence
                remaining = fs_id.sequence_remaining
                remaining_percent = fs_id.remaining_percentage
                seq_length = fs_id.sequence_end - fs_id.sequence_start + 1
                consumed_percent = round(1 - (remaining / seq_length), 2) * 100
                if consumed_percent < remaining_percent:
                    inv.l10n_do_fiscal_sequence_status = "fiscal_ok"
                elif remaining > 0 and consumed_percent >= remaining_percent:
                    inv.l10n_do_fiscal_sequence_status = "almost_no_sequence"
                else:
                    inv.l10n_do_fiscal_sequence_status = "no_sequence"

    @api.constrains("state", "invoice_line_ids", "partner_id")
    def validate_products_export_ncf(self):
        """ Validates that an invoices with a partner from country != DO
            and products type != service must have Exportaciones NCF.
            See DGII Norma 05-19, Art 10 for further information.
        """
        for inv in self:
            if (
                inv.move_type == "out_invoice"
                and inv.state in ("posted", "cancel")
                and inv.partner_id.country_id
                and inv.partner_id.country_id.code != "DO"
                and inv.l10n_latam_use_documents
            ):
                if any([p for p in inv.invoice_line_ids.mapped("product_id") if p.type != "service"]):
                    if (
                        ncf_dict.get(inv.l10n_latam_document_type_id.doc_code_prefix) in (
                        "exterior", "e-exterior")
                    ):
                        raise UserError(_("Goods sales to overseas customers must have " "Exportaciones Fiscal Type"))
                elif (
                    ncf_dict.get(inv.l10n_latam_document_type_id.doc_code_prefix) not in ("consumo", "e-consumer")
                ):
                    raise UserError(_("Service sales to overseas customer must have " "Consumo Fiscal Type"))

    @api.constrains("state", "tax_line_ids")
    def validate_informal_withholding(self):
        """ Validates an invoice with Comprobante de Compras has 100% ITBIS
            withholding.
            See DGII Norma 05-19, Art 7 for further information.
        """
        for inv in self.filtered(lambda i: i.move_type == "in_invoice" and i.state == "posted"):
            if (ncf_dict.get(inv.l10n_latam_document_type_id.doc_code_prefix) in ("informal", "e-informal")
                and inv.l10n_latam_use_documents
            ):
                # If the sum of all taxes of category ITBIS is not 0
                if sum(
                    [
                        tax.amount
                        for tax in inv.tax_line_ids.mapped("tax_id").filtered(
                        lambda t: t.purchase_tax_type in ['itbis', 'ritbis'])
                    ]
                ):
                    raise UserError(_("You must withhold 100% of ITBIS"))

    @api.constrains('state', 'tax_line_ids')
    def validate_special_exempt(self):
        """ Validates an invoice with Regímenes Especiales sale_fiscal_type
            does not contain nor ITBIS or ISC.
            See DGII Norma 05-19, Art 3 for further information.
        """
        for inv in self:
            if inv.l10n_latam_use_documents:
                if (
                    inv.move_type == 'out_invoice'
                    and inv.state in ('posted', 'cancel')
                    and inv.l10n_latam_document_type_id.l10n_do_ncf_type
                    and 'special' in inv.l10n_latam_document_type_id.l10n_do_ncf_type
                ):

                    # If any invoice tax in ITBIS or ISC
                    if any([
                        tax for tax in inv.tax_line_ids.mapped('tax_id').filtered(
                            lambda tax: tax.tax_group_id.name in ('ITBIS', 'ISC') and tax.amount != 0)
                    ]):
                        raise UserError(_(
                            "No puede validar una factura para Regímen Especial "
                            " con ITBIS/ISC.\n\n"
                            "Consulte Norma General 05-19, Art. 3 de la DGII")
                        )

    def _post(self, soft=True):
        """ After all invoice validation routine, consume a NCF sequence and
            write it into ref field.
        """
        res = super()._post(soft)
        for inv in self:
            non_payer_type_invoices = self.filtered(
                lambda i: i.company_id.country_id == self.env.ref("base.do")
                          and i.l10n_latam_use_documents
                          and not i.partner_id.l10n_do_dgii_tax_payer_type
            )

            if non_payer_type_invoices:
                raise ValidationError(_("Fiscal invoices require partner fiscal type: %s" % inv.name))
                _logger.info("Fiscal invoices require partner fiscal type: " + inv.name)

            if inv.l10n_latam_use_documents:
                # Because a Fiscal Sequence can be depleted while an invoice
                # is waiting to be validated, compute fiscal_sequence_id again
                # on invoice validate.
                inv._compute_l10n_do_fiscal_sequence()
                if not inv.l10n_latam_document_number and not inv.l10n_do_fiscal_sequence_id:
                    raise ValidationError(_(
                        "There is not active Sequence for "
                        "{}"
                    ).format(inv.l10n_latam_document_type_id.name))

        for inv in self:
            if inv.l10n_latam_use_documents and res and inv.l10n_do_fiscal_sequence_id:
                inv.write(
                    {
                        "l10n_do_ncf_expiration_date": inv.l10n_do_fiscal_sequence_id.expiration_date,
                    }
                )

                if not inv.l10n_latam_document_number:
                    document_number = inv.l10n_do_fiscal_sequence_id.get_fiscal_number()
                    inv.state = "draft"
                    inv.write(
                        {
                            "state": "posted",
                            "l10n_latam_document_number": document_number,
                            "payment_reference": '%s - %s' % (inv.name, document_number),
                        }
                    )

        return res

    @api.depends('l10n_latam_document_type_id', 'journal_id')
    def _compute_l10n_latam_manual_document_number(self):
        """ Indicates if this document type uses a sequence or if the numbering is made manually """
        recs_with_journal_id = self.filtered(lambda x: x.journal_id and x.journal_id.l10n_latam_use_documents)
        for rec in recs_with_journal_id:
            if rec.move_type in ["in_refund"] and rec.l10n_do_origin_ncf:
                credit_origin_id = self.env["account.move"].sudo().search(
                    [("l10n_latam_document_number", "=", rec.l10n_do_origin_ncf)], limit=1
                )
                if credit_origin_id.l10n_latam_document_type_id.l10n_do_ncf_type in ["e-minor", "e-informal", "e-exterior"]:
                    rec.l10n_latam_manual_document_number = False
                else:
                    rec.l10n_latam_manual_document_number = rec._is_manual_document_number()
            else:
                rec.l10n_latam_manual_document_number = rec._is_manual_document_number()
        remaining = self - recs_with_journal_id
        remaining.l10n_latam_manual_document_number = False

    def _compute_l10n_latam_amount_and_taxes(self):
        recs_invoice = self.filtered(lambda x: x.is_invoice())
        for invoice in recs_invoice:
            tax_lines = invoice.line_ids.filtered('tax_line_id')
            currencies = invoice.line_ids.filtered(lambda x: x.currency_id == invoice.currency_id).mapped('currency_id')
            included_taxes = invoice.l10n_latam_document_type_id and \
                             invoice.l10n_latam_document_type_id._filter_taxes_included(tax_lines.mapped('tax_line_id'))
            if not included_taxes:
                l10n_latam_amount_untaxed = invoice.amount_untaxed
                not_included_invoice_taxes = tax_lines
            else:
                included_invoice_taxes = tax_lines.filtered(lambda x: x.tax_line_id in included_taxes)
                not_included_invoice_taxes = tax_lines - included_invoice_taxes
                if invoice.is_inbound():
                    sign = -1
                else:
                    sign = 1
                amount = 'amount_currency' if len(currencies) == 1 else 'balance'
                l10n_latam_amount_untaxed = invoice.amount_untaxed + sign * sum(included_invoice_taxes.mapped(amount))
            invoice.l10n_latam_amount_untaxed = l10n_latam_amount_untaxed
            invoice.l10n_latam_tax_ids = not_included_invoice_taxes
        remaining = self - recs_invoice
        remaining.l10n_latam_amount_untaxed = False
        remaining.l10n_latam_tax_ids = [(5, 0)]

    @api.depends('journal_id', 'partner_id', 'company_id', 'move_type')
    def _compute_l10n_latam_available_document_types(self):
        self.l10n_latam_available_document_type_ids = False
        for rec in self.filtered(lambda x: x.journal_id and x.journal_id.l10n_latam_use_documents and x.partner_id):
            rec.l10n_latam_available_document_type_ids = self.env['l10n_latam.document.type'].search(
                rec._get_l10n_latam_documents_domain())

    @api.depends('l10n_latam_available_document_type_ids', 'debit_origin_id')
    def _compute_l10n_latam_document_type(self):
        for rec in self.filtered(lambda x: x.state == 'draft'):
            document_types = rec.l10n_latam_available_document_type_ids._origin
            invoice_type = rec.move_type
            if invoice_type in ['out_refund', 'in_refund']:
                document_types = document_types.filtered(lambda x: x.internal_type not in ['debit_note', 'invoice'])
            elif invoice_type in ['out_invoice', 'in_invoice']:
                document_types = document_types.filtered(lambda x: x.internal_type not in ['credit_note'])
            if rec.debit_origin_id:
                document_types = self.env["l10n_latam.document.type"].search([]).filtered(
                    lambda x: x.internal_type == 'debit_note')
                if self.company_id.l10n_do_ecf_issuer:
                    document_types = document_types.filtered(lambda x: x.l10n_do_ncf_type == 'e-debit_note')

            rec.l10n_latam_document_type_id = document_types and document_types[0].id

    @api.constrains('name', 'partner_id', 'company_id', 'posted_before')
    def _check_unique_vendor_number(self):
        """ The constraint _check_unique_sequence_number is valid for customer bills but not valid for us on vendor
        bills because the uniqueness must be per partner """
        for rec in self.filtered(
                lambda x: x.name and x.name != '/' and x.is_purchase_document() and x.l10n_latam_use_documents):
            domain = [
                ('move_type', '=', rec.move_type),
                # by validating name we validate l10n_latam_document_type_id
                ('name', '=', rec.name),
                ('company_id', '=', rec.company_id.id),
                ('id', '!=', rec.id),
                ('commercial_partner_id', '=', rec.commercial_partner_id.id),
                # allow to have to equal if they are cancelled
                ('state', '!=', 'cancel'),
            ]
            if rec.search(domain):
                raise ValidationError(_('Vendor bill number must be unique per vendor and company.'))

    def unlink(self):
        """ When using documents, on vendor bills the document_number is set manually by the number given from the vendor,
        the odoo sequence is not used. In this case We allow to delete vendor bills with document_number/move_name """
        self.filtered(lambda x: x.move_type in x.get_purchase_types() and x.state in (
            'draft', 'cancel') and x.l10n_latam_use_documents).write({'name': '/'})
        return super().unlink()
