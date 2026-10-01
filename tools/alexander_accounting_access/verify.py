# Verify Geilin has full Accounting. Does not post invoices.
import json

out = {"ok": True, "errors": []}
geilin = env["res.users"].sudo().search(
    [("login", "=", "geilin.rosario@inversionesdoralex.com")], limit=1
)
flags = {
    "invoice": geilin.has_group("account.group_account_invoice"),
    "user": geilin.has_group("account.group_account_user"),
    "basic": geilin.has_group("account.group_account_basic"),
    "manager": geilin.has_group("account.group_account_manager"),
    "validate_bank": geilin.has_group("account.group_validate_bank_account"),
    "fiscal_user": geilin.has_group("justech_l10n_do_base.group_justech_do_fiscal_user"),
    "system": geilin.has_group("base.group_system"),
    "erp_manager": geilin.has_group("base.group_erp_manager"),
}
out["flags"] = flags
for key in ("manager", "user", "basic", "invoice", "validate_bank"):
    if not flags[key]:
        out["ok"] = False
        out["errors"].append("missing %s" % key)
if flags["system"] or flags["erp_manager"]:
    out["ok"] = False
    out["errors"].append("settings groups were granted")

as_user = geilin
Move = env["account.move"].with_user(as_user).with_company(11).with_context(
    allowed_company_ids=geilin.company_ids.ids
)
Journal = env["account.journal"].with_user(as_user).with_company(11).with_context(
    allowed_company_ids=geilin.company_ids.ids
)
Account = env["account.account"].with_user(as_user).with_company(11).with_context(
    allowed_company_ids=geilin.company_ids.ids
)
try:
    out["journals"] = Journal.search_count([("company_id", "=", 11)])
    out["accounts"] = Account.search_count([("company_id", "=", 11)])
    inv = Move.browse(163)
    out["invoice_163"] = {"name": inv.name, "state": inv.state, "ncf": inv.justech_do_ncf}
    if inv.state != "posted" or inv.justech_do_ncf != "B1500000152":
        out["ok"] = False
        out["errors"].append("invoice 163 changed")
except Exception as err:  # noqa: BLE001
    out["ok"] = False
    out["errors"].append("%s:%s" % (type(err).__name__, err))

mod = env["ir.module.module"].sudo().search(
    [("name", "=", "justech_alexander_base")], limit=1
)
out["module"] = mod.latest_version
frozen = env["ir.module.module"].sudo().search(
    [("name", "=", "justech_purchase_sale_margin_control")], limit=1
)
out["margin_module"] = frozen.latest_version

print("GEILIN_ACCOUNTING_VERIFY_BEGIN")
print(json.dumps(out, default=str, indent=2, ensure_ascii=False))
print("GEILIN_ACCOUNTING_VERIFY_END")
if not out["ok"]:
    raise SystemExit("GEILIN_ACCOUNTING_VERIFY=FAIL")
env.cr.rollback()
