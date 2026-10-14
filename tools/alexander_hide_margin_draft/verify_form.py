# ruff: noqa
"""Confirm margin UI hidden and Reset to draft visible. Read-only."""


def run(env):
    move = env["account.move"].sudo().search([("name", "=", "INV/2026/00025")], limit=1)
    if not move:
        move = (
            env["account.move"]
            .sudo()
            .search(
                [("move_type", "=", "out_invoice"), ("state", "=", "posted")],
                limit=1,
            )
        )
    user = (
        env["res.users"]
        .sudo()
        .search([("login", "=", "elianny.sanchez@inversionesdoralex.com")], limit=1)
    )
    geilin = (
        env["res.users"]
        .sudo()
        .search([("login", "=", "geilin.rosario@inversionesdoralex.com")], limit=1)
    )
    print("MOVE", move.name, move.state, move.company_id.name)
    for actor in (user, geilin):
        if not actor:
            continue
        arch = (
            env["account.move"]
            .with_user(actor)
            .with_company(move.company_id)
            .with_context(
                lang=actor.lang or "es_DO",
                allowed_company_ids=[move.company_id.id],
            )
            .get_view(view_type="form")
            .get("arch")
            or ""
        )
        print("USER", actor.login)
        print(
            "HAS_RESET",
            'name="button_draft"' in arch and "Restablecer a borrador" in arch,
        )
        print("HAS_ANULAR", 'string="Anular"' in arch)
        i_corr = arch.find("action_open_correct_invoice_wizard")
        i_void = arch.find("action_open_void_ncf_wizard")
        print(
            "CORREGIR_HIDDEN",
            i_corr < 0 or 'invisible="1"' in arch[i_corr : i_corr + 220],
        )
        print(
            "ANULAR_NCF_HIDDEN",
            i_void < 0 or 'invisible="1"' in arch[i_void : i_void + 220],
        )
        print(
            "HAS_GESTIONAR_VISIBLE",
            "action_manage_purchases" in arch
            and 'invisible="1"'
            not in arch.split("action_manage_purchases", 1)[-1][:80],
        )
        print(
            "PANEL_INVISIBLE",
            'name="margin_out_panel"' not in arch or 'invisible="1"' in arch,
        )
        print("HAS_DRAFT_BTN", 'name="button_draft"' in arch)
        idx = arch.find('name="button_draft"')
        print(
            "DRAFT_SNIP",
            (
                arch[max(0, idx - 20) : idx + 180].replace("\n", " ")
                if idx >= 0
                else "MISSING"
            ),
        )
        idx2 = arch.find('name="margin_out_panel"')
        print(
            "PANEL_SNIP",
            (
                arch[max(0, idx2 - 20) : idx2 + 160].replace("\n", " ")
                if idx2 >= 0
                else "ABSENT"
            ),
        )
    mod = (
        env["ir.module.module"]
        .sudo()
        .search([("name", "=", "justech_purchase_sale_margin_control")], limit=1)
    )
    menu = env.ref(
        "justech_purchase_sale_margin_control.menu_purchase_sale_margin_root",
        raise_if_not_found=False,
    )
    ux = (
        env["ir.module.module"]
        .sudo()
        .search([("name", "=", "justech_alexander_ux")], limit=1)
    )
    base = (
        env["ir.module.module"]
        .sudo()
        .search([("name", "=", "justech_alexander_base")], limit=1)
    )
    print(
        "MARGIN_APPLICATION",
        mod.application,
        "MENU_ACTIVE",
        menu.active if menu else None,
    )
    print("UX_VERSION", ux.latest_version, "BASE_VERSION", base.latest_version)
    arch_ok = (
        env["account.move"]
        .with_user(user or geilin)
        .with_company(move.company_id)
        .with_context(lang="es_DO", allowed_company_ids=[move.company_id.id])
        .get_view(view_type="form")
        .get("arch")
        or ""
    )
    i_corr = arch_ok.find("action_open_correct_invoice_wizard")
    i_void = arch_ok.find("action_open_void_ncf_wizard")
    ok = (
        not mod.application
        and menu
        and not menu.active
        and ux.latest_version.endswith("1.6.13")
        and 'string="Anular"' in arch_ok
        and (i_corr < 0 or 'invisible="1"' in arch_ok[i_corr : i_corr + 220])
        and (i_void < 0 or 'invisible="1"' in arch_ok[i_void : i_void + 220])
    )
    print("VERIFY", "PASS" if ok else "FAIL")
    return ok


run(env)
