"""Delete test customer invoices so they no longer appear.

PROD: never unlink posted invoices (opening baseline stays).
STAGING: may cancel+unlink posted documents whose partner is a QA/test label.
Does not send mail, DGII or e-CF.
"""
import json
import os
import re

APPLY = os.environ.get("ODOO_DELETE_TEST_INVOICES") == "1"
DB = env.cr.dbname
IS_PROD = DB == "doralex_prod"

TEST_PARTNER = re.compile(
    r"(dx\s*test|dxqa|dx-qa|no fiscal real|opready|created by:\s*fausto)",
    re.I,
)
PINARIA_DRAFT_AMOUNTS = {50.0, 100.0}

companies = env["res.company"].sudo().search([])
Move = env["account.move"].sudo().with_context(
    active_test=False,
    allowed_company_ids=companies.ids,
    tracking_disable=True,
    mail_notrack=True,
    mail_create_nolog=True,
)


def _is_test_partner(partner):
    text = " ".join(
        filter(
            None,
            [
                partner.name,
                partner.display_name,
                partner.ref,
                getattr(partner, "comment", None),
            ],
        )
    )
    return bool(TEST_PARTNER.search(text or ""))


def _is_pinaria_leftover_draft(move):
    if move.state != "draft" or move.move_type not in ("out_invoice", "out_refund"):
        return False
    if move.name not in (False, "/", ""):
        return False
    partner = (move.partner_id.name or "").upper()
    amount = round(float(move.amount_total or 0.0), 2)
    return (
        "PIÑARIA" in partner or "PINARIA" in partner
    ) and amount in PINARIA_DRAFT_AMOUNTS


def _is_empty_draft(move):
    return (
        move.state == "draft"
        and move.move_type
        in ("out_invoice", "out_refund", "in_invoice", "in_refund")
        and not move.partner_id
        and not move.invoice_line_ids
        and not move.amount_total
    )


INVOICE_TYPES = ("out_invoice", "out_refund", "in_invoice", "in_refund")

candidates = Move.browse()
for move in Move.search([("move_type", "in", list(INVOICE_TYPES))]):
    if _is_test_partner(move.partner_id) or _is_pinaria_leftover_draft(move) or _is_empty_draft(
        move
    ):
        candidates |= move

if IS_PROD:
    blocked = candidates.filtered(lambda m: m.state == "posted")
    candidates = candidates - blocked
else:
    blocked = Move.browse()

report = {
    "database": DB,
    "apply": APPLY,
    "prod_guard": IS_PROD,
    "candidate_ids": candidates.ids,
    "candidate_count": len(candidates),
    "blocked_posted_prod": [
        {"id": m.id, "name": m.name, "partner": m.partner_id.display_name}
        for m in blocked
    ],
    "deleted": [],
    "errors": [],
    "posted_before": Move.search_count(
        [("move_type", "=", "out_invoice"), ("state", "=", "posted")]
    ),
}

if APPLY:
    for move in candidates:
        key = {
            "id": move.id,
            "name": move.name,
            "state": move.state,
            "type": move.move_type,
            "partner": move.partner_id.display_name,
            "company": move.company_id.name,
        }
        try:
            rec = move
            if rec.state == "posted":
                rec.button_draft()
                rec = rec.exists()
            if rec.exists() and rec.state not in ("draft", "cancel"):
                rec.button_cancel()
                rec = rec.exists()
            if rec.exists():
                rec.unlink()
            report["deleted"].append(key)
        except Exception as exc:  # noqa: BLE001
            key["error"] = str(exc)[:240]
            report["errors"].append(key)
    env.cr.commit()

report["posted_after"] = Move.search_count(
    [("move_type", "=", "out_invoice"), ("state", "=", "posted")]
)
left = [
    {
        "id": m.id,
        "type": m.move_type,
        "state": m.state,
        "partner": m.partner_id.display_name,
        "company": m.company_id.name,
    }
    for m in Move.search([("move_type", "in", list(INVOICE_TYPES))])
    if _is_test_partner(m.partner_id)
]
report["remaining_test"] = len(left)
report["remaining_rows"] = left
report["companies_scanned"] = companies.mapped("name")
print(json.dumps(report, indent=2, default=str, ensure_ascii=False))
