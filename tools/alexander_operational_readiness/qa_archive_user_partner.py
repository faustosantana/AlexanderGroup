# ruff: noqa
"""Archiva partner 48 del usuario QA ya inactivo."""


def run(env):
    u = env["res.users"].with_context(active_test=False).browse(7)
    if hasattr(u, "action_archive"):
        try:
            u.sudo().action_archive()
        except Exception as exc:  # noqa: BLE001
            print("action_archive_user", exc)
    env.cr.execute("UPDATE res_users SET active = false WHERE id = 7")
    env.cr.execute("UPDATE res_partner SET active = false WHERE id = 48")
    env.cr.commit()
    env.invalidate_all()
    u = env["res.users"].with_context(active_test=False).browse(7)
    p = env["res.partner"].with_context(active_test=False).browse(48)
    print(
        json_dumps := __import__("json").dumps(
            {
                "user_active": u.active,
                "partner_active": p.active,
                "partner_name": p.name,
            }
        )
    )


if "env" in globals():
    run(env)
