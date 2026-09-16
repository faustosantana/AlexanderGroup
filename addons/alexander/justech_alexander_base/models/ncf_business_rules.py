"""H09 — el padrón DGII no bloquea facturación ni contactos."""

from odoo import models

_PADRON_BLOCK_MARKERS = (
    "pendiente de validar",
    "requiere revisión fiscal",
    "valide el rnc",
    "valide con padrón",
    "confirme histórico o valide con padrón",
    "sin comprobante fiscal resoluble",
)


class JustechDoNcfBusinessRulesService(models.AbstractModel):
    _inherit = "justech.do.ncf.business.rules.service"

    def validate_before_post(self, move):
        """Conserva B14 / monto alto / exportación. Omite exigencia de padrón."""
        move.ensure_one()
        from odoo.exceptions import UserError

        try:
            return super().validate_before_post(move)
        except UserError as exc:
            text = str(exc).lower()
            if any(marker in text for marker in _PADRON_BLOCK_MARKERS):
                return None
            raise
