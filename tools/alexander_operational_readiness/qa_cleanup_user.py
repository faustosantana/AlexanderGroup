# ruff: noqa
"""Cierra el partner del usuario QA. No toca apertura."""

import json
from pathlib import Path

OUT = "/tmp/op_ready_qa_user.json"


def run(env):
    u = env["res.users"].with_context(active_test=False).browse(7)
    rec = {"user_before": {"id": u.id, "login": u.login, "active": u.active}}
    if u.exists():
        u.sudo().write({"active": False})
        env.cr.commit()
        u.invalidate_recordset()
        rec["user_after"] = {"active": u.active}
        partner = u.partner_id
        rec["partner"] = {
            "id": partner.id,
            "name": partner.name,
            "active": partner.active,
        }
        if partner.active:
            try:
                partner.sudo().write({"active": False})
                rec["partner_archived"] = True
            except Exception as exc:  # noqa: BLE001
                rec["partner_error"] = str(exc)
    leftover = (
        env["res.partner"]
        .with_context(active_test=True)
        .search(
            [
                "|",
                ("name", "ilike", "DX TEST"),
                ("name", "ilike", "NO FISCAL REAL"),
            ]
        )
    )
    rec["active_qa_partners"] = [{"id": p.id, "name": p.name} for p in leftover]
    rec["active_qa_users"] = [
        {"id": x.id, "login": x.login, "active": x.active}
        for x in env["res.users"].search(
            ["|", ("login", "ilike", "dx.test"), ("name", "ilike", "DX TEST")]
        )
    ]
    env.cr.commit()
    Path(OUT).write_text(json.dumps(rec, indent=2, ensure_ascii=False, default=str))
    print(json.dumps(rec, indent=2, ensure_ascii=False, default=str))


if "env" in globals():
    run(env)
