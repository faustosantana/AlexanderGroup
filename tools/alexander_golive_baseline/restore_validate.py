# Isolated restore validation. No HTTP, no mail, no DGII, no e-CF.
env = env  # noqa: F821
assert env.cr.dbname == "doralex_restore_golive_20260926", env.cr.dbname
print("DB", env.cr.dbname)
cr = env.cr
cr.execute("UPDATE ir_cron SET active=false")
print("CRON_DISABLED", cr.rowcount)
if "ir.mail_server" in env:
    servers = env["ir.mail_server"].sudo().search([])
    if servers:
        servers.write({"active": False})
    print("MAIL_SERVERS_DISABLED", len(servers))
for key, val in (
    ("mail.catchall.domain", ""),
    ("mail.bounce.alias", "noreply-restore"),
):
    rec = env["ir.config_parameter"].sudo().search([("key", "=", key)], limit=1)
    if rec:
        rec.value = val
print("COMPANIES", [(c.id, c.name) for c in env["res.company"].sudo().search([])])
print("USERS", env["res.users"].sudo().search_count([("share", "=", False)]))
print(
    "TMPL",
    env["product.template"].sudo().with_context(active_test=False).search_count([]),
)
print("POSTED", env["account.move"].sudo().search_count([("state", "=", "posted")]))
print("SO", env["sale.order"].sudo().search_count([]))
print("PO", env["purchase.order"].sudo().search_count([]))
print("ATTACH", env["ir.attachment"].sudo().search_count([]))
print("QWEB", env["ir.ui.view"].sudo().search_count([("type", "=", "qweb")]))
for login in (
    "alexander.pina@inversionesdoralex.com",
    "luis.aquino@inversionesdoralex.com",
    "geilin.rosario@inversionesdoralex.com",
):
    u = env["res.users"].sudo().search([("login", "=", login)], limit=1)
    print(
        "LOGIN", login, "id", u.id if u else 0, "active", bool(u.active) if u else False
    )
cr.execute(
    "SELECT count(*) FROM account_move WHERE ref ILIKE %s AND state='posted'",
    ("%ALEXANDER_OPENING%",),
)
print("OPENING_POSTED", cr.fetchone()[0])
ctx = {"active_test": False}
T = env["product.template"].sudo().with_context(**ctx)
for name in ("Agregado grueso (grava) 3/4", "Servicios profesionales"):
    rec = T.search([("name", "=", name)], limit=1)
    if rec:
        print(
            "FOCUS",
            rec.id,
            rec.name,
            rec.type,
            rec.active,
            rec.list_price,
            rec.sale_ok,
            rec.purchase_ok,
        )
# Sample stored attachment exists on disk
atts = env["ir.attachment"].sudo().search([("store_fname", "!=", False)], limit=3)
ok = 0
import os

for a in atts:
    path = "/var/lib/odoo/filestore/%s/%s" % (env.cr.dbname, a.store_fname)
    exists = os.path.exists(path)
    print("FS_FILE", a.store_fname, exists, a.file_size)
    if exists:
        ok += 1
print("FILESTORE_SAMPLES_OK", ok)
print("RESTORE_REGISTRY_OK")
