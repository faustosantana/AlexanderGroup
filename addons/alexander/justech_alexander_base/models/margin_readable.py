"""Invoice/SO/PO forms must load even if the user cannot see the MTX.

Geilin has margin Ventas, so the sales-scope record rule hides MTX whose
salesperson is someone else (Elianny). After posting, the form web_reads
margin_transaction_ids and raises AccessError on a document that is already
posted. Keep only MTX ids the real user can search; never grant groups or
open extra record rules.
"""

from odoo import models
from odoo.exceptions import AccessError

_MTX_MODEL = "purchase.sale.margin.transaction"
_MTX_FIELD = "margin_transaction_ids"


def _dx_keep_readable_mtx(records):
    if _MTX_MODEL not in records.env or _MTX_FIELD not in records._fields:
        return
    Tx = records.env[_MTX_MODEL]
    field = records._fields[_MTX_FIELD]
    for rec in records:
        try:
            ids = rec[_MTX_FIELD].ids
        except AccessError:
            rec.env.cache.set(rec, field, ())
            if "margin_transaction_count" in rec._fields:
                rec.margin_transaction_count = 0
            continue
        if not ids:
            continue
        allowed = tuple(Tx.search([("id", "in", ids)]).ids)
        if allowed != tuple(ids):
            rec.env.cache.set(rec, field, allowed)
            if "margin_transaction_count" in rec._fields:
                rec.margin_transaction_count = len(allowed)


def _dx_web_read_without_forbidden_mtx(recordset, specification, super_read):
    spec = dict(specification or {})
    if _MTX_FIELD in spec:
        _dx_keep_readable_mtx(recordset)
    try:
        return super_read(spec)
    except AccessError as err:
        if _MTX_MODEL not in str(err) or _MTX_FIELD not in spec:
            raise
        spec.pop(_MTX_FIELD, None)
        return super_read(spec)


class AccountMove(models.Model):
    _inherit = "account.move"

    def web_read(self, specification):
        return _dx_web_read_without_forbidden_mtx(self, specification, super().web_read)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def web_read(self, specification):
        return _dx_web_read_without_forbidden_mtx(self, specification, super().web_read)


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def web_read(self, specification):
        return _dx_web_read_without_forbidden_mtx(self, specification, super().web_read)
