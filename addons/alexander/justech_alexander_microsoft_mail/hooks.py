def post_init_hook(env):
    env["res.company"].sudo()._dx_bootstrap_microsoft_mail()
