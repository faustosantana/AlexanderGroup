# ruff: noqa
"""Verify GET / as Elianny with Mayuma-only switcher. Read-only."""

from odoo.http import root


def run(env):
    user = env["res.users"].sudo().browse(15)
    session = root.session_store.new()
    session["db"] = env.cr.dbname
    session["uid"] = user.id
    session["login"] = user.login
    session["session_token"] = user._compute_session_token(session.sid)
    session["context"] = {
        "lang": "es_DO",
        "uid": user.id,
        "allowed_company_ids": [12],
    }
    root.session_store.save(session)
    open("/tmp/dx_elianny_sid", "w").write(session.sid)
    print("SESSION_WRITTEN", user.login, "db", env.cr.dbname)
    return True


run(env)
