import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class DxMsInboundMessage(models.Model):
    _name = "dx.ms.inbound.message"
    _description = "Cursor de correo entrante Microsoft"
    _order = "id desc"

    graph_id = fields.Char(required=True, index=True)
    mailbox = fields.Char(required=True, index=True)
    internet_message_id = fields.Char(index=True)
    company_id = fields.Many2one("res.company", required=True, index=True)
    route = fields.Char()
    state = fields.Selection(
        [("done", "Procesado"), ("error", "Error"), ("skip", "Omitido")],
        default="done",
        required=True,
    )
    attempts = fields.Integer(default=1)
    last_error = fields.Char()

    _sql_constraints = [
        ("graph_unique", "unique(graph_id)", "El mensaje Graph ya fue registrado.")
    ]

    @api.model
    def _cron_fetch(self):
        client = self.env["dx.ms.graph.client"]
        if not client.configured():
            _logger.info("Microsoft Graph secrets not mounted; inbound cron skipped")
            return True
        companies = (
            self.env["res.company"].sudo().search([("dx_mail_mailbox", "!=", False)])
        )
        for company in companies:
            self._fetch_company(company, client)
        return True

    def _fetch_company(self, company, client):
        mailbox = company.dx_mail_mailbox
        try:
            messages = client.list_inbox(mailbox)
        except Exception:
            _logger.exception("Graph inbox failed company=%s", company.dx_short_code)
            return
        for item in messages:
            graph_id = item.get("id")
            if not graph_id:
                continue
            if self.sudo().search([("graph_id", "=", graph_id)], limit=1):
                continue
            self._ingest(company, client, item)

    def _ingest(self, company, client, item):
        graph_id = item.get("id")
        mailbox = company.dx_mail_mailbox
        mime = b""
        try:
            mime = client.get_mime(mailbox, graph_id)
            if not mime:
                raise ValueError("empty MIME")
            self.env["mail.thread"].with_company(company).with_context(
                default_company_id=company.id,
                company_id=company.id,
            ).message_process(False, mime)
            client.mark_read(mailbox, graph_id)
            self.sudo().create(
                {
                    "graph_id": graph_id,
                    "mailbox": mailbox,
                    "internet_message_id": item.get("internetMessageId"),
                    "company_id": company.id,
                    "route": (item.get("subject") or "")[:128],
                    "state": "done",
                }
            )
        except Exception as exc:
            _logger.exception(
                "Inbound Graph ingest failed company=%s", company.dx_short_code
            )
            existing = self.sudo().search([("graph_id", "=", graph_id)], limit=1)
            vals = {
                "graph_id": graph_id,
                "mailbox": mailbox,
                "internet_message_id": item.get("internetMessageId"),
                "company_id": company.id,
                "state": "error",
                "last_error": str(exc)[:200],
            }
            if existing:
                existing.write(
                    {
                        "state": "error",
                        "attempts": existing.attempts + 1,
                        "last_error": vals["last_error"],
                    }
                )
            else:
                self.sudo().create(vals)
