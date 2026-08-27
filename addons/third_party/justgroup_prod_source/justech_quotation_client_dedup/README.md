# Justech Quotation Client Dedup

Minimal QWeb hotfix: quotations show the customer once (box under the title),
not again under the company header.

## Deploy (DEV first)

```bash
# update module only — never -u all
odoo -c /opt/odoo-dev/conf/odoo-dev.conf -d justech_dev -i justech_quotation_client_dedup --stop-after-init
```

## Rollback

Uninstall the module or restore the pre-change `ir_ui_view` / DB backup.
After uninstall, the standard `t-set="address"` block returns.
