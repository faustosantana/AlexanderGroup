"""Guardia de posteo fiscal: sin rango NCF real no se contabiliza.

Si el rango existe pero el vencimiento Excel ya pasó, el error debe decir
que el NCF está vencido para que lo validen. No crea rangos ni reutiliza
numeración de otra empresa.
"""

from odoo import _, fields, models
from odoo.exceptions import UserError

_NCF_GUARD_MSG = "Debe configurar un rango NCF válido para esta compañía y tipo de comprobante antes de contabilizar."

_MISSING_RANGE_MARKERS = (
    "No hay rango NCF activo",
    "Debe indicar o asignar un NCF",
    "no tiene habilitado el Motor NCF",
    "No existe un rango DGII activo",
)

QA_MIN = 99100000


class JustechDoNcfAssignmentService(models.AbstractModel):
    _inherit = "justech.do.ncf.assignment.service"

    def _alexander_raise_if_expired_range(self, moves):
        Range = self.env["justech.do.ncf.range"]
        resolver = self.env["justech.do.ncf.document.type.resolver.service"]
        today = fields.Date.context_today(self)
        fiscal = self.env["justech.do.fiscal.config.service"]
        for move in moves.filtered(lambda m: m.state == "draft"):
            if not fiscal.is_fiscal_enabled(move.company_id):
                continue
            if move.justech_do_ncf_voided:
                continue
            if move.move_type not in (
                "out_invoice",
                "out_refund",
                "out_debit",
                "in_invoice",
                "in_refund",
            ):
                continue
            doc = move.justech_do_document_type_id
            if not doc:
                try:
                    doc = resolver.resolve_for_move(move)
                except Exception:  # noqa: BLE001
                    continue
            if not doc:
                continue
            rng = Range.search(
                [
                    ("company_id", "=", move.company_id.id),
                    ("document_type_id", "=", doc.id),
                    ("sequence_start", "<", QA_MIN),
                ],
                limit=1,
            )
            if not rng:
                continue
            if rng.state == "expired" or (rng.date_to and today > rng.date_to):
                raise UserError(
                    _(
                        "El rango NCF %(prefix)s de %(company)s está vencido "
                        "(vence %(date_to)s). No se puede facturar hasta validarlo.",
                        prefix=rng.prefix,
                        company=move.company_id.display_name,
                        date_to=rng.date_to,
                    )
                )

    def assign_before_post(self, moves):
        self._alexander_raise_if_expired_range(moves)
        try:
            return super().assign_before_post(moves)
        except UserError as exc:
            text = str(exc)
            if "está vencido" in text:
                raise
            if any(marker in text for marker in _MISSING_RANGE_MARKERS):
                raise UserError(_(_NCF_GUARD_MSG)) from exc
            raise
