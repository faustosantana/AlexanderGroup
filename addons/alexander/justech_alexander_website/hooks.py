def post_init_hook(env):
    website = env.ref("website.default_website", raise_if_not_found=False)
    doralex = (
        env["res.company"]
        .sudo()
        .search(
            [("dx_short_code", "=", "DOR")],
            limit=1,
        )
    )
    if website:
        vals = {
            "name": "Doralex Group",
        }
        if doralex:
            vals["company_id"] = doralex.id
            if doralex.logo:
                vals["logo"] = doralex.logo
        website.write(vals)
    page = env.ref("website.homepage_page", raise_if_not_found=False)
    if page:
        page.write(
            {
                "website_meta_title": "Doralex Group | Alexander Group",
                "website_meta_description": (
                    "Grupo empresarial dominicano. Comercio, servicios, "
                    "alimentos, agroindustria e inversión."
                ),
                "website_meta_keywords": (
                    "Doralex, Alexander Group, República Dominicana, "
                    "Piñaria, Dominion, El Mayuma, Rempart, Blue Elite"
                ),
            }
        )
    contact = env.ref("website.contactus_page", raise_if_not_found=False)
    if contact:
        contact.write(
            {
                "website_meta_title": "Contacto | Doralex Group",
                "website_meta_description": (
                    "Contacto institucional de Doralex Group en República Dominicana."
                ),
            }
        )
    if website and website.menu_id:
        Menu = env["website.menu"].sudo()
        existing = Menu.search(
            [("website_id", "=", website.id), ("url", "=", "/#empresas")],
            limit=1,
        )
        if not existing:
            Menu.create(
                {
                    "name": "Empresas",
                    "url": "/#empresas",
                    "parent_id": website.menu_id.id,
                    "website_id": website.id,
                    "sequence": 30,
                }
            )
            Menu.create(
                {
                    "name": "Grupo",
                    "url": "/#grupo",
                    "parent_id": website.menu_id.id,
                    "website_id": website.id,
                    "sequence": 20,
                }
            )
