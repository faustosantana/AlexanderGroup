# Verify company-bank trust. Does not post invoices or consume NCF.
import json

out = {"ok": True, "errors": []}
Bank = env["res.partner.bank"].sudo()
companies = env["res.company"].sudo().search([])
partner_ids = companies.mapped("partner_id").ids
company_banks = Bank.search([("partner_id", "in", partner_ids)])
other_banks = Bank.search([("partner_id", "not in", partner_ids)])

trusted = []
untrusted = []
for bank in company_banks:
    row = {
        "id": bank.id,
        "partner": bank.partner_id.name,
        "allow_out_payment": bank.allow_out_payment,
        "company_owned": bank._dx_is_company_owned_bank(),
    }
    if bank.allow_out_payment:
        trusted.append(row)
    else:
        untrusted.append(row)
        out["ok"] = False
        out["errors"].append("company bank %s still untrusted" % bank.id)

out["company_banks_total"] = len(company_banks)
out["company_banks_trusted"] = len(trusted)
out["company_banks_untrusted"] = untrusted
out["other_banks"] = [
    {
        "id": bank.id,
        "partner": bank.partner_id.name,
        "allow_out_payment": bank.allow_out_payment,
    }
    for bank in other_banks
]
if any(bank.allow_out_payment for bank in other_banks):
    out["ok"] = False
    out["errors"].append("non-company bank was trusted")

mod = env["ir.module.module"].sudo().search(
    [("name", "=", "justech_alexander_base")], limit=1
)
out["module"] = {"state": mod.state, "latest_version": mod.latest_version}

geilin = env["res.users"].sudo().search(
    [("login", "=", "geilin.rosario@inversionesdoralex.com")], limit=1
)
out["geilin"] = None
if geilin:
    out["geilin"] = {
        "id": geilin.id,
        "has_validate_bank": geilin.has_group(
            "account.group_validate_bank_account"
        ),
        "has_account_manager": geilin.has_group("account.group_account_manager"),
        "has_system": geilin.has_group("base.group_system"),
        "has_invoice": geilin.has_group("account.group_account_invoice"),
    }
    if out["geilin"]["has_validate_bank"] or out["geilin"]["has_account_manager"]:
        out["ok"] = False
        out["errors"].append("geilin groups were widened")

so = env["sale.order"].sudo().search([("name", "=", "DOR/SO/00030")], limit=1)
moves = so.invoice_ids if so else env["account.move"]
out["invoice"] = None
for move in moves:
    bank = move.partner_bank_id
    would_block = bool(
        bank and move.is_inbound() and not bank.allow_out_payment
    )
    row = {
        "id": move.id,
        "state": move.state,
        "move_type": move.move_type,
        "is_inbound": move.is_inbound(),
        "ncf": move.justech_do_ncf if "justech_do_ncf" in move._fields else None,
        "partner_bank_id": bank.id if bank else False,
        "allow_out_payment": bank.allow_out_payment if bank else None,
        "would_block_untrusted_bank": would_block,
    }
    out["invoice"] = row
    if move.state != "draft":
        continue
    if would_block:
        out["ok"] = False
        out["errors"].append("draft invoice %s still blocked by bank trust" % move.id)
    if geilin and move.state == "draft":
        as_user = move.with_user(geilin).with_company(move.company_id).with_context(
            allowed_company_ids=geilin.company_ids.ids
        )
        try:
            as_user._dx_trust_inbound_company_banks()
            bank2 = as_user.partner_bank_id
            user_block = bool(
                bank2 and as_user.is_inbound() and not bank2.allow_out_payment
            )
            can_trust = bool(bank2.with_user(geilin)._user_can_trust()) if bank2 else None
            row["as_geilin_would_block"] = user_block
            row["as_geilin_user_can_trust"] = can_trust
            if user_block:
                out["ok"] = False
                out["errors"].append("geilin still blocked on invoice %s" % move.id)
        except Exception as err:  # noqa: BLE001
            row["as_geilin_error"] = "%s:%s" % (type(err).__name__, err)
            out["ok"] = False
            out["errors"].append(row["as_geilin_error"])

print("BANK_TRUST_VERIFY_BEGIN")
print(json.dumps(out, default=str, indent=2, ensure_ascii=False))
print("BANK_TRUST_VERIFY_END")
if not out["ok"]:
    raise SystemExit("BANK_TRUST_VERIFY=FAIL")
env.cr.commit()
