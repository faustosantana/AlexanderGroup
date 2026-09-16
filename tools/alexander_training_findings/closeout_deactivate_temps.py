assert env.cr.dbname == "doralex_ent_staging"
Users = env["res.users"].sudo().with_context(active_test=False)
for login in (
    "dxuat.sales.only@example.invalid",
    "dxuat.billing@example.invalid",
):
    user = Users.search([("login", "=", login)], limit=1)
    if user and user.active:
        user.active = False
    print("USER", login, "active", user.active if user else None)
env.cr.commit()
print("DEACTIVATED")
