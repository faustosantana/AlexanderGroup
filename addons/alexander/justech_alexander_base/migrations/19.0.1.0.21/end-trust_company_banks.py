def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {"install_mode": True})
    env["res.partner.bank"]._dx_trust_company_owned_banks()
