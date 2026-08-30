# Reaplica catálogo y nombres de menú al actualizar el overlay (post_init solo corre al instalar).


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    from odoo.addons.justech_alexander_ux.hooks import (
        _apply_catalog,
        _apply_menu_names,
    )

    env = api.Environment(cr, SUPERUSER_ID, {})
    _apply_catalog(env)
    _apply_menu_names(env)
