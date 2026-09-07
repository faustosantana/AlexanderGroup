"""Read-only inventory of test and leftover customer invoices."""
import json

companies = env["res.company"].sudo().search([])
Move = env["account.move"].sudo().with_context(
    active_test=False, allowed_company_ids=companies.ids
)
Partner = env["res.partner"].sudo()
ncf_field = (
    "l10n_latam_document_number"
    if "l10n_latam_document_number" in Move._fields
    else "ref"
)


def row(m):
    return {
        "id": m.id,
        "name": m.name,
        "state": m.state,
        "move_type": m.move_type,
        "partner": m.partner_id.display_name,
        "partner_id": m.partner_id.id,
        "company": m.company_id.name,
        "ncf": m[ncf_field] or "",
        "amount": float(m.amount_total or 0),
        "date": str(m.invoice_date or m.date),
    }


test_partners = Partner.search(
    [
        "|",
        "|",
        "|",
        "|",
        "|",
        ("name", "ilike", "test"),
        ("name", "ilike", "fiscal real"),
        ("name", "ilike", "dx test"),
        ("display_name", "ilike", "test"),
        ("ref", "ilike", "TEST"),
        ("comment", "ilike", "Created by"),
    ]
)
test_moves = Move.search(
    [
        ("move_type", "in", ["out_invoice", "out_refund"]),
        "|",
        "|",
        ("partner_id", "in", test_partners.ids or [0]),
        ("name", "ilike", "RINV/"),
        ("ref", "ilike", "TEST"),
    ]
)
cancelled = Move.search(
    [
        ("move_type", "in", ["out_invoice", "out_refund"]),
        ("state", "=", "cancel"),
    ]
)
drafts = Move.search(
    [
        ("move_type", "in", ["out_invoice", "out_refund"]),
        ("state", "=", "draft"),
    ]
)
posted = Move.search(
    [
        ("move_type", "in", ["out_invoice", "out_refund"]),
        ("state", "=", "posted"),
    ]
)
print(
    json.dumps(
        {
            "posted_count": len(posted),
            "draft_count": len(drafts),
            "cancelled_count": len(cancelled),
            "test_partners": [
                {"id": p.id, "name": p.name, "display": p.display_name}
                for p in test_partners
            ],
            "test_moves": [row(m) for m in test_moves],
            "cancelled": [row(m) for m in cancelled],
            "drafts": [row(m) for m in drafts],
            "posted_sample": [row(m) for m in posted[:40]],
        },
        indent=2,
        default=str,
        ensure_ascii=False,
    )
)
