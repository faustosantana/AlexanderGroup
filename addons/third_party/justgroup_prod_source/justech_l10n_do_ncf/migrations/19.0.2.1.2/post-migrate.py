import logging

_logger = logging.getLogger(__name__)

STANDARD_RANGE_NAMES = {
    "B01": "B01 Factura de Crédito Fiscal",
    "B02": "B02 Factura de Consumo",
    "B03": "B03 Nota de Débito",
    "B04": "B04 Nota de Crédito",
    "B11": "B11 Comprobante de Compras",
    "B13": "B13 Gastos Menores",
    "B14": "B14 Regímenes Especiales de Tributación",
    "B15": "B15 Comprobante Gubernamental",
    "B17": "B17 Comprobante para Pagos al Exterior",
}


def migrate(cr, version):
    from odoo import api

    env = api.Environment(cr, 1, {})
    Range = env["justech.do.ncf.range"].sudo()
    tokens = ("rollout", "std", "test", "dev", "piloto", "gate")
    updated = 0
    for prefix, standard_name in STANDARD_RANGE_NAMES.items():
        for rng in Range.search([("prefix", "=", prefix)]):
            name = (rng.name or "").lower()
            if any(t in name for t in tokens) or not (rng.name or "").startswith(prefix):
                rng.name = standard_name
                updated += 1
    _logger.info("justech_l10n_do_ncf: normalized %s NCF range names", updated)
