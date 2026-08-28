def post_init_hook(env):
    admin = env.ref("base.user_admin", raise_if_not_found=False)
    Access = env["justech.admin.access"]
    if admin:
        Access.ensure_access_shell(admin, company=admin.company_id)
        doralex = env["res.company"].search([("dx_short_code", "=", "DOR")], limit=1)
        if doralex:
            Access.ensure_access_shell(admin, company=doralex)
