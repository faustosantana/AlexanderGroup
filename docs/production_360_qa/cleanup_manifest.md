# Inventario QA y cleanup (NO ejecutado)

`QA CLEANUP: PREPARED = YES · EXECUTED = NO`  
`TEST NCF CLEANUP: PREPARED = YES · EXECUTED = NO`

Catálogo exacto (IDs): [`qa_catalog.json`](qa_catalog.json)

Scripts (no-op sin `CONFIRM=yes`):

- `tools/production_360_qa/cleanup_production_qa.py`
- `tools/production_360_qa/remove_test_ncf_configuration.py`

## Conteos

| Bucket | Count |
| --- | --- |
| partners (clientes+proveedores+tag) | 13 |
| products | 3 |
| ncf_ranges TEST | 12 |
| sale.order | 10 |
| purchase.order | 10 |
| account.move | 48 |
| account.payment | 22 |
| stock.picking | 21 |
| crm.lead | 4 |
| justech.warranty | 4–5 (re-runs) |
| res.users QA | 1 (`dx.test.security@justech.do`) |

Ningún partner QA es cliente/proveedor comercial real.  
Ningún rango TEST usa autorización DGII.  
Moves TEST: `justech_do_include_in_dgii=False`.

## Próximo prompt

FREEZE → BACKUP → ejecutar cleanup → remove TEST NCF → verificar DB limpia → cargar NCF reales → primera factura real.
