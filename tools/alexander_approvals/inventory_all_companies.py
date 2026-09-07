"""List leftover customer/vendor invoices that look like QA leftovers, all companies."""
import json
import re

TEST = re.compile(
    r"(dx\s*test|dxqa|dx-qa|no fiscal real|opready|created by:\s*fausto|qa approval)",
    re.I,
)
companies = env["res.company"].sudo().search([])
Move = env["account.move"].sudo().with_context(
    active_test=False, allowed_company_ids=companies.ids
)
ncf = (
    "l10n_latam_document_number"
    if "l10n_latam_document_number" in Move._fields
    else "ref"
)


def row(m):
    return {
        "id": m.id,
        "name": m.name,
        "state": m.state,
        "type": m.move_type,
        "partner": m.partner_id.display_name,
        "company": m.company_id.name,
        "ncf": m[ncf] or "",
        "amount": float(m.amount_total or 0),
    }


all_moves = Move.search([("move_type", "in", ["out_invoice", "out_refund", "in_invoice", "in_refund"])])
suspects = []
by_company = {}
for m in all_moves:
    text = " ".join(
        filter(
            None,
            [
                m.partner_id.name,
                m.partner_id.display_name,
                m.partner_id.ref,
                getattr(m.partner_id, "comment", None),
                m.narration and str(m.narration),
                m.ref,
                m.name,
            ],
        )
    )
    pinaria_draft = (
        m.state == "draft"
        and m.move_type in ("out_invoice", "out_refund")
        and m.name in (False, "/", "")
        and ("PIÑARIA" in (m.partner_id.name or "").upper() or "PINARIA" in (m.partner_id.name or "").upper())
    )
    empty_draft = (
        m.state == "draft"
        and m.move_type in ("out_invoice", "out_refund", "in_invoice", "in_refund")
        and not m.partner_id
        and not m.amount_total
    )
    if TEST.search(text or "") or pinaria_draft or empty_draft:
        suspects.append(row(m))
    key = m.company_id.name
    by_company.setdefault(
        key,
        {"posted_out": 0, "draft_out": 0, "cancel_out": 0, "all": 0},
    )
    by_company[key]["all"] += 1
    if m.move_type in ("out_invoice", "out_refund"):
        if m.state == "posted":
            by_company[key]["posted_out"] += 1
        elif m.state == "draft":
            by_company[key]["draft_out"] += 1
        elif m.state == "cancel":
            by_company[key]["cancel_out"] += 1

print(
    json.dumps(
        {
            "db": env.cr.dbname,
            "companies": [c.name for c in companies],
            "by_company": by_company,
            "suspect_count": len(suspects),
            "suspects": suspects,
            "posted_out_invoices": Move.search_count(
                [("move_type", "=", "out_invoice"), ("state", "=", "posted")]
            ),
        },
        indent=2,
        default=str,
        ensure_ascii=False,
    )
)
