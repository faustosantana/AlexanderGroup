# 16 — Backups / restore

Latest PROD backup (real files, not "cron exists"):

`/opt/odoo-backups/pre_fix_multicompany_tax_access_20260926_133358`

| artifact | bytes |
|---|---:|
| db/doralex_prod.dump | 27131887 |
| db/pg_restore.list | 3021449 (TOC 34029) |
| filestore/odoo_data.tar | 205035520 |
| custom-addons/custom-addons.tar | 19824640 |
| config/odoo.conf | 1620 |

No `/etc/cron.d` Odoo dump job. Backups are agent/manual `pre_*` directories.

RESTORE_TEST = PASS on isolated DB `doralex_restore_golive_20260926` in staging-db (never touched `doralex_prod` / `doralex_ent_staging`):

- pg_restore RC=0, TOC=34029, 1554 public tables, 7 companies, 1750 templates, 29 posted
- filestore 818 files; 3 stored attachment samples existed on disk
- Odoo shell started; cron disabled (83 jobs); mail servers 0
- Login rows resolved (Alexander/Luis/Geilin)
- Opening posted moves = 2
- Focus 21 consu / 168 service 0.00
- Copy dropped after validation

NON_BLOCKING: install a scheduled backup (DB+filestore+addons+config), not only manual `pre_*`.
