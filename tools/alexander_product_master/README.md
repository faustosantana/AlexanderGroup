# Alexander product master catalog

Construye un catálogo limpio a partir de los Excel históricos de cotización.
No importa una fila por producto. No escribe en Odoo durante el dry-run.

## Dry-run (local, sin Odoo)

```bash
python3 tools/alexander_product_master/dump_odoo_products.py   # vía run_odoo_shell.sh
python3 tools/alexander_product_master/build_master.py \
  --odoo-json /tmp/odoo_products.json
```

Salida: `docs/enterprise_conversion/evidence/alexander_product_master_20260907/`

## Aplicar (staging / producción, ORM)

1. Backup `pre_alexander_product_master_import_<timestamp>` y `pg_restore -l`.
2. Staging primero. Si QA pasa, el mismo payload en producción.
3. El apply rematch por identidad en el destino. No reutiliza IDs de staging.

```bash
tools/alexander_m365_users/run_odoo_shell.sh staging \
  tools/alexander_product_master/apply_odoo.py
```

`PRODUCT_MASTER_DRY=1` evita escrituras.
`PRODUCT_MASTER_PAYLOAD` apunta al JSON de productos auto-importables.
