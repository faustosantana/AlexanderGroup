# Verify invoice 163 form loads as Geilin. Does not post or consume NCF.
import json

out = {"ok": True, "errors": []}
move = env["account.move"].sudo().browse(163)
geilin = env["res.users"].sudo().browse(17)
elianny = env["res.users"].sudo().browse(15)
out["invoice"] = {
    "id": move.id,
    "name": move.name,
    "state": move.state,
    "ncf": move.justech_do_ncf,
}
if move.state != "posted":
    out["ok"] = False
    out["errors"].append("invoice is not posted")
if move.justech_do_ncf != "B1500000152":
    out["ok"] = False
    out["errors"].append("NCF changed: %s" % move.justech_do_ncf)

spec = {
    "id": {},
    "name": {},
    "state": {},
    "display_name": {},
    "margin_transaction_ids": {"fields": {"display_name": {}}},
    "margin_transaction_count": {},
}


def _read_as(user):
    rec = (
        env["account.move"]
        .with_user(user)
        .with_company(move.company_id)
        .with_context(allowed_company_ids=user.company_ids.ids)
        .browse(163)
    )
    return rec.web_read(spec)


try:
    geo = _read_as(geilin)[0]
    out["geilin_web_read"] = {
        "state": geo.get("state"),
        "name": geo.get("name"),
        "mtx_ids": geo.get("margin_transaction_ids"),
    }
    if geo.get("state") != "posted":
        out["ok"] = False
        out["errors"].append("geilin does not see posted state")
except Exception as err:  # noqa: BLE001
    out["ok"] = False
    out["errors"].append("geilin web_read: %s:%s" % (type(err).__name__, err))

try:
    eli = _read_as(elianny)[0]
    out["elianny_web_read"] = {
        "state": eli.get("state"),
        "mtx_ids": eli.get("margin_transaction_ids"),
    }
except Exception as err:  # noqa: BLE001
    out["ok"] = False
    out["errors"].append("elianny web_read: %s:%s" % (type(err).__name__, err))

mod = env["ir.module.module"].sudo().search(
    [("name", "=", "justech_alexander_base")], limit=1
)
out["module"] = mod.latest_version
frozen = env["ir.module.module"].sudo().search(
    [("name", "=", "justech_purchase_sale_margin_control")], limit=1
)
out["margin_module"] = frozen.latest_version
if "19.0.8.29.38" not in (frozen.latest_version or ""):
    out["ok"] = False
    out["errors"].append("margin module version changed")

print("MARGIN_FORM_VERIFY_BEGIN")
print(json.dumps(out, default=str, indent=2, ensure_ascii=False))
print("MARGIN_FORM_VERIFY_END")
if not out["ok"]:
    raise SystemExit("MARGIN_FORM_VERIFY=FAIL")
env.cr.rollback()
