# Documentación técnica — Justech Garantías

## Modelos
### `justech.warranty`
- Hereda `mail.thread`, `mail.activity.mixin`.
- Campos clave: `partner_id`, `product_id`, `lot_id`, `warranty_months`,
  `date_start`, `date_end` (compute store), `state`, `invoice_id`, `invoice_line_id`,
  `sale_order_id`, `company_id`.
- Restricciones:
  - `unique(lot_id)`: una garantía por serie/lote.
  - `_check_serial_required`: exige `lot_id` cuando el producto se rastrea por serie
    y el estado es `active`/`claimed`.
- Secuencia: `justech.warranty` (`GAR/%(year)s/#####`).
- Cron: `_cron_expire_warranties()` marca `active → expired` cuando `date_end < hoy`.

### `justech.warranty.claim`
- Relacionado 1:N con `justech.warranty` (`ondelete=cascade`).
- Campos `related` almacenados: `partner_id`, `product_id`, `lot_id`, `company_id`.
- Secuencia: `justech.warranty.claim` (`RMA/%(year)s/#####`).

### Extensiones
- `product.template.warranty_months` + `has_warranty` (compute store).
- `account.move._post()`: tras publicar, `_generate_warranties()` crea garantías para
  facturas `out_invoice`. Idempotente por `invoice_line_id` (evita duplicados).

## Seguridad
- Grupos: `group_warranty_user`, `group_warranty_manager` (implica user).
- `ir.model.access.csv`: user (CRU), manager (CRUD).
- Reglas `ir.rule` multi-compañía (globales) sobre ambos modelos.

## Puntos de extensión previstos (fases siguientes)
- Certificado PDF de garantía (con `justech_report_base` neutro).
- Portal del cliente para consulta de garantías.
- Generación opcional desde entrega (`stock.picking`).

## Pruebas
`tests/test_warranty.py`: cálculo de vencimiento, serie obligatoria, cron de
vencimiento, resolución de reclamo y generación desde factura (idempotente).

## Rollback
- Desinstalar el módulo elimina modelos, vistas, grupos, secuencias y cron.
- Los campos añadidos a `product.template`/`account.move` se retiran al desinstalar.
- Cambios versionados en rama `feature/justgroup-standard-base` (revertibles vía Git).
