# ruff: noqa
"""Asigna la contraseña temporal de Odoo a Alexander (uid 5).

Implementación nueva: no había acceso Odoo previo que él conociera.
No imprime la contraseña. No toca __system__. No envía email de reset.
"""

from __future__ import annotations

import json
import os

PASSWORD = os.environ.get("ODOO_TEMP_PASSWORD")
EXPECTED_LOGIN = "alexander.pina@inversionesdoralex.com"
EXPECTED_ID = 5


def main():
    if not PASSWORD:
        raise SystemExit("ODOO_TEMP_PASSWORD missing")
    env2 = env(
        context=dict(
            env.context,
            no_reset_password=True,
            tracking_disable=True,
            mail_create_nolog=True,
            mail_notrack=True,
        )
    )
    user = env2["res.users"].with_context(active_test=False).browse(EXPECTED_ID)
    if not user.exists():
        raise SystemExit("ALEXANDER_USER_MISSING")
    if user.id == 1:
        raise SystemExit("REFUSES_SUPERUSER")
    if user.login != EXPECTED_LOGIN:
        raise SystemExit("LOGIN_MISMATCH:%s" % user.login)
    if hasattr(user, "_change_password"):
        user._change_password(PASSWORD)
    else:
        user.write({"password": PASSWORD})
    env2.cr.commit()
    report = {
        "USER_ID": user.id,
        "LOGIN": user.login,
        "PASSWORD_SET": True,
        "superuser_id_1_touched": False,
    }
    print(json.dumps(report, indent=2))


main()
