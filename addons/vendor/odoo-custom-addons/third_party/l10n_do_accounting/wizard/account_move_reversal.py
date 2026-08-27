from odoo import models, api, fields, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    l10n_latam_use_documents = fields.Boolean(compute='_compute_document_type')
    l10n_latam_document_type_id = fields.Many2one('l10n_latam.document.type', 'Document Type', ondelete='cascade',
                                                  domain="[('id', 'in', l10n_latam_available_document_type_ids)]",
                                                  compute='_compute_document_type', readonly=False)
    l10n_latam_available_document_type_ids = fields.Many2many('l10n_latam.document.type',
                                                              compute='_compute_document_type')
    l10n_latam_document_number = fields.Char(string='Document Number')
    l10n_latam_manual_document_number = fields.Boolean(compute='_compute_l10n_latam_manual_document_number',
                                                       string='Manual Number')

    @api.depends('l10n_latam_document_type_id')
    def _compute_l10n_latam_manual_document_number(self):
        self.l10n_latam_manual_document_number = False
        for rec in self.filtered('move_ids'):
            move = rec.move_ids[0]
            if move.journal_id and move.journal_id.l10n_latam_use_documents:
                rec.l10n_latam_manual_document_number = move._is_manual_document_number()

    @api.model
    def _reverse_type_map(self, move_type):
        match = {
            'entry': 'entry',
            'out_invoice': 'out_refund',
            'in_invoice': 'in_refund',
            'in_refund': 'in_invoice',
            'out_receipt': 'in_receipt',
            'in_receipt': 'out_receipt'}
        return match.get(move_type)

    @api.depends('move_ids')
    def _compute_document_type(self):
        self.l10n_latam_available_document_type_ids = False
        self.l10n_latam_document_type_id = False
        self.l10n_latam_use_documents = False
        for record in self:
            if len(record.move_ids) > 1:
                move_ids_use_document = record.move_ids._origin.filtered(lambda move: move.l10n_latam_use_documents)
                if move_ids_use_document:
                    raise UserError(
                        _('You can only reverse documents with legal invoicing documents from Latin America one at a time.\nProblematic documents: %s') % ", ".join(
                            move_ids_use_document.mapped('name')))
            else:
                record.l10n_latam_use_documents = record.move_ids.journal_id.l10n_latam_use_documents

            if record.l10n_latam_use_documents:
                refund = record.env['account.move'].new({
                    'move_type': record._reverse_type_map(record.move_ids.move_type),
                    'journal_id': record.move_ids.journal_id.id,
                    'partner_id': record.move_ids.partner_id.id,
                    'company_id': record.move_ids.company_id.id,
                })
                record.l10n_latam_document_type_id = refund.l10n_latam_document_type_id
                record.l10n_latam_available_document_type_ids = refund.l10n_latam_available_document_type_ids

    def _prepare_default_reversal(self, move):
        """ Set the default document type and number in the new revsersal move taking into account the ones selected in
        the wizard """
        res = super()._prepare_default_reversal(move)
        if self.country_code == 'DO' and move.l10n_latam_use_documents:
            res.update({
                'l10n_latam_document_type_id': self.l10n_latam_document_type_id.id,
                'l10n_do_origin_ncf': move.l10n_latam_document_number,
                'l10n_do_ecf_modification_code': self.l10n_do_ecf_modification_code,
            })

        return res

    @api.onchange('l10n_latam_document_number', 'l10n_latam_document_type_id')
    def _onchange_l10n_latam_document_number(self):
        if self.l10n_latam_document_type_id:
            l10n_latam_document_number = self.l10n_latam_document_type_id._format_document_number(
                self.l10n_latam_document_number)
            if self.l10n_latam_document_number != l10n_latam_document_number:
                self.l10n_latam_document_number = l10n_latam_document_number

    @api.model
    def _default_account(self):
        move_type = self._context.get("type")
        journal = (
            self.env["account.move"]
            .with_context(
                default_type=move_type, default_company_id=self.env.company.id
            )
            ._get_default_journal()
        )
        if move_type in ("out_invoice", "in_refund"):
            return journal.default_credit_account_id.id
        return journal.default_debit_account_id.id

    l10n_latam_country_code = fields.Char(
        related="company_id.l10n_do_country_code",
        help="Technical field used to hide/show fields regarding the localization",
    )

    l10n_do_ecf_modification_code = fields.Selection(
        selection=lambda self: self.env[
            "account.move"
        ]._get_l10n_do_ecf_modification_code(),
        string="e-CF Modification Code",
        copy=False,
    )
    is_ecf_invoice = fields.Boolean(
        string="Is Electronic Invoice",
    )
  
    @api.model
    def default_get(self, fields_list):
        res = super(AccountMoveReversal, self).default_get(fields_list)
        move_ids = (
            self.env["account.move"].browse(self.env.context["active_ids"])
            if self.env.context.get("active_model") == "account.move"
            else self.env["account.move"]
        )
        move_ids_use_document = move_ids.filtered(
            lambda move: move.l10n_latam_use_documents
            and move.company_id.l10n_do_country_code == "DO"
        )

        if len(move_ids_use_document) > 1:
            raise UserError(
                _(
                    "You cannot create Credit Notes from multiple "
                    "documents at a time."
                )
            )
        if move_ids_use_document:
            res["is_ecf_invoice"] = move_ids_use_document[0].is_ecf_invoice

        res["l10n_do_ecf_modification_code"] = "1"
        return res
