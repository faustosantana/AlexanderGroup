from odoo import api, models


class MailComposeMessage(models.TransientModel):
    _inherit = "mail.compose.message"

    def _dx_role_address(self):
        self.ensure_one()
        res_ids = self._evaluate_res_ids() or []
        company = self.record_company_id
        model = self.model
        res_id = res_ids[0] if len(res_ids) == 1 else None
        if model and model in self.env and res_id:
            record = self.env[model].sudo().browse(res_id)
            if record.exists() and "company_id" in record._fields and record.company_id:
                company = record.company_id
        if not company or not company.dx_mail_domain:
            return ""
        return company._dx_mail_identity(model, res_id)

    def _compute_authorship(self):
        super()._compute_authorship()
        for composer in self:
            addr = composer._dx_role_address()
            if addr:
                composer.email_from = addr

    def _compute_reply_to(self):
        super()._compute_reply_to()
        for composer in self:
            addr = composer._dx_role_address()
            if addr:
                composer.reply_to = addr
                composer.reply_to_force_new = True

    @api.depends(
        "composition_mode",
        "model",
        "parent_id",
        "res_domain",
        "res_ids",
        "subtype_id",
        "template_id",
    )
    def _compute_partner_ids(self):
        super()._compute_partner_ids()
        for composer in self:
            if composer.partner_ids or composer.composition_batch:
                continue
            res_ids = composer._evaluate_res_ids() or []
            if (
                not composer.model
                or composer.model not in self.env
                or len(res_ids) != 1
            ):
                continue
            record = self.env[composer.model].sudo().browse(res_ids[0])
            if not record.exists() or "partner_id" not in record._fields:
                continue
            partner = record.partner_id
            if partner and partner.email:
                composer.partner_ids = partner
