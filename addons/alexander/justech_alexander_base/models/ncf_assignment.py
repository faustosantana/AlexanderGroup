"""Guardia de posteo fiscal: sin rango NCF real no se contabiliza.

No crea rangos, no inventa NCF y no reutiliza numeración de otra empresa.
El motor Justech sigue asignando cuando existe un rango activo válido.
"""

from odoo import _, models
from odoo.exceptions import UserError

_NCF_GUARD_MSG = "Debe configurar un rango NCF válido para esta compañía y tipo de comprobante antes de contabilizar."

_MISSING_RANGE_MARKERS = (
    "No hay rango NCF activo",
    "Debe indicar o asignar un NCF",
    "no tiene habilitado el Motor NCF",
)


class JustechDoNcfAssignmentService(models.AbstractModel):
    _inherit = "justech.do.ncf.assignment.service"

    def assign_before_post(self, moves):
        try:
            return super().assign_before_post(moves)
        except UserError as exc:
            text = str(exc)
            if any(marker in text for marker in _MISSING_RANGE_MARKERS):
                raise UserError(_(_NCF_GUARD_MSG)) from exc
            raise
