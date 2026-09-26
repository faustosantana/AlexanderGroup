# Render official reports on existing staging documents. No mail/DGII.
env = env  # noqa: F821
import json

OUT = "/tmp/golive_report_qa.json"
report = {"renders": [], "MAIL_SENT": 0, "errors": []}
mail_before = env["mail.mail"].sudo().search_count([]) if "mail.mail" in env else 0


def _xmlids():
    candidates = {
        "quotation": [
            "justech_alexander_reports.action_report_sale_quotation",
            "sale.action_report_saleorder",
        ],
        "purchase": [
            "justech_alexander_reports.action_report_purchase_order",
            "purchase.action_report_purchase_order",
        ],
        "invoice": [
            "justech_alexander_reports.action_report_account_move",
            "account.account_invoices",
        ],
        "conduce": [
            "justech_alexander_reports.action_report_conduce",
            "stock.action_report_delivery",
        ],
    }
    found = {}
    for key, xmls in candidates.items():
        for xml in xmls:
            rec = env.ref(xml, raise_if_not_found=False)
            if rec:
                found[key] = rec
                break
    return found


actions = _xmlids()
report["actions"] = {
    k: a.xml_id if hasattr(a, "xml_id") else a.display_name for k, a in actions.items()
}

so = (
    env["sale.order"]
    .sudo()
    .search([("state", "in", ("draft", "sent", "sale"))], limit=3, order="id desc")
)
po = (
    env["purchase.order"]
    .sudo()
    .search([("state", "in", ("draft", "purchase"))], limit=3, order="id desc")
)
inv = (
    env["account.move"]
    .sudo()
    .search(
        [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "in", ("draft", "posted")),
        ],
        limit=3,
        order="id desc",
    )
)
pick = (
    env["stock.picking"]
    .sudo()
    .search([("picking_type_code", "=", "outgoing")], limit=3, order="id desc")
)

pairs = [
    ("quotation", so, actions.get("quotation")),
    ("purchase", po, actions.get("purchase")),
    ("invoice", inv, actions.get("invoice")),
    ("conduce", pick, actions.get("conduce")),
]
for kind, recs, action in pairs:
    row = {"kind": kind, "docs": [], "ok": 0, "fail": 0}
    if not action:
        row["error"] = "NO_ACTION"
        report["renders"].append(row)
        continue
    for rec in recs:
        item = {"id": rec.id, "name": rec.display_name, "company": rec.company_id.id}
        try:
            pdf, ext = env["ir.actions.report"].sudo()._render_qweb_pdf(action, rec.ids)
            item["bytes"] = len(pdf or b"")
            item["ext"] = ext
            item["ok"] = bool(pdf)
            row["ok"] += 1 if item["ok"] else 0
            row["fail"] += 0 if item["ok"] else 1
        except Exception as exc:  # noqa: BLE001
            item["ok"] = False
            item["error"] = type(exc).__name__
            item["msg"] = str(exc)[:200]
            row["fail"] += 1
        row["docs"].append(item)
    report["renders"].append(row)

mail_after = env["mail.mail"].sudo().search_count([]) if "mail.mail" in env else 0
report["MAIL_SENT"] = max(0, mail_after - mail_before)
report["QWEB_TOTAL"] = env["ir.ui.view"].sudo().search_count([("type", "=", "qweb")])
report["REPORTS_RENDER_QA"] = (
    "PASS"
    if all(
        r.get("ok", 0) > 0 and r.get("fail", 0) == 0
        for r in report["renders"]
        if r.get("error") != "NO_ACTION"
    )
    else "PARTIAL"
)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(report, fh, ensure_ascii=False, default=str, indent=2)
print(
    "WROTE",
    OUT,
    report["REPORTS_RENDER_QA"],
    "MAIL",
    report["MAIL_SENT"],
    "QWEB",
    report["QWEB_TOTAL"],
)
for r in report["renders"]:
    print("RENDER", r["kind"], "ok", r.get("ok"), "fail", r.get("fail"), r.get("error"))
