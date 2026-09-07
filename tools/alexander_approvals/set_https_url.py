"""Set HTTPS public approval URL from web.base.url or a known host. No document writes."""
icp = env["ir.config_parameter"].sudo()
current = icp.get_param("justech.approval.public.base.url") or ""
web = icp.get_param("web.base.url") or ""
chosen = current
if not chosen.startswith("https://"):
    if web.startswith("https://"):
        chosen = web
    elif "enterprise" in web or "staging" in web:
        chosen = "https://enterprise.doralexgroup.cloud"
    else:
        chosen = "https://doralexgroup.cloud"
    icp.set_param("justech.approval.public.base.url", chosen)
    env.cr.commit()
print("public_url", chosen)
print("web_base_url", web)
