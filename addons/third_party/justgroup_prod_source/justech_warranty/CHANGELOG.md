# Changelog — justech_warranty

Formato basado en [Keep a Changelog](https://keepachangelog.com/) y SemVer Odoo
(`19.0.MAJOR.MINOR.PATCH`).

## [19.0.1.9.1] - 2026-07-14
### Fixed
- **Descripción editable en líneas de cotización/pedido:** se restablece
  `sale.order.line.name` (`widget="sol_text"`) con `optional="show"` (estándar
  Odoo 19). La vista de garantías lo había dejado en `optional="hide"` al
  compactar la grilla, ocultando la columna de descripción y bloqueando la
  edición libre multilínea tras elegir producto.

## [19.0.1.9.0] - 2026-07-13
### Added
- **Modelo `justech.warranty.unit`**: unidad trazable individualmente dentro de
  una garantía comercial. Fields: `serial_manufacturer`, `serial_internal`,
  `serial_state`, `vendor_id`, `purchase_order_id`, `vendor_bill_id`,
  `customer_warranty_months`, `vendor_warranty_months`, `coverage_gap_months`,
  `coverage_risk`, `delivery_mode`, entre otros. Serial de fabricante único por
  compañía (constraint Python).
- **Multi-unidad**: `qty=10` en la línea comercial genera hasta 10 unidades de
  garantía al postear la factura. Cada unidad puede tener su propio serial.
- **Configuración pre-guardado (NewId)**: el widget OWL `warranty_config_button`
  ahora se habilita cuando hay producto aunque la línea no exista en BD. Para
  líneas nuevas abre el wizard, y al aplicar reenvía los valores al front vía
  `ir.actions.act_window_close.infos` para aplicarlos con `record.update`.
- **Cobertura cliente vs. proveedor**: campos `vendor_id`, `vendor_warranty_months`,
  `vendor_date_start/end` y `coverage_gap_months` tanto en `justech.warranty`
  como en `justech.warranty.unit`.
- **Reclamos parciales**: `justech.warranty.claim.unit_ids` (Many2many).
  Al resolver un reclamo sólo se marcan como reclamadas las unidades indicadas;
  el header pasa a `claimed` sólo si todas sus unidades quedan reclamadas.
- **Enlace opcional compra**: `purchase_order_id`, `purchase_line_id`,
  `vendor_bill_id`, `vendor_bill_line_id` en la unidad de garantía.
- **Modo de entrega** (`delivery_mode`) en la unidad: entrega directa,
  entrega desde proveedor, retiro cliente, parcial, completada, cancelada.
- **Seriales planificados** en la línea comercial (`warranty_planned_serials`,
  texto libre — uno por renglón). Al postear la factura se aplican en orden a
  las unidades generadas.
- Vistas, menú **Unidades / Seriales**, ACLs, rule multi-compañía y secuencia
  `GARU/AÑO/000000` para las unidades.
### Changed
- **Dependencia `stock` removida**. `stock.lot` desaparece de `justech.warranty`
  y `justech.warranty.unit`. El serial primario vive en `serial_manufacturer`.
  Un módulo puente futuro (`justech_warranty_stock`) integrará con inventario.
- **Dependencia `purchase` añadida** para enlazar orden/factura de proveedor.
- `justech.warranty.quantity` ahora significa **unidades esperadas** en la garantía.
- `_sql_constraints.lot_unique` eliminado. En su lugar, unicidad de
  `serial_manufacturer` por compañía en `justech.warranty.unit`.
- `certificate_ready` se calcula ahora en función del serial en las unidades.
- `justech.warranty.claim.lot_id` eliminado; se reemplaza por
  `serial_manufacturer` computado a partir de `unit_ids`.
### Removed
- Campo `lot_id` en `justech.warranty` (schema migration OK — 0 registros en DEV).
- Template XML duplicado `static/src/xml/warranty_config_button_field.xml`
  (el widget usa template inline).

## [19.0.1.8.0] - 2026-07-09
### Changed
- Garantía en línea: **una sola columna** con icono 🛡 (sin toggle, resumen ni columnas extra).
- Modal con estado visible: Configurada / Sin garantía / Pendiente.
- Cotización/factura: oculta columna Unidad; descuento visible; menos columnas = sin scroll horizontal.
- Eliminado patch JS del toggle en grilla.

## [19.0.1.7.1] - 2026-07-09
### Fixed
- Defaults de meses/tipo al crear línea con `warranty_apply=True` (cotización y factura).
- Onchange de producto precarga tipo vía mixin.

## [19.0.1.7.0] - 2026-07-09
### Fixed
- Acción del wizard con `ir.actions.act_window` completo (`views`, `view_id`) para Odoo 19;
  corrige `TypeError: Cannot read properties of undefined (reading 'map')`.
- Modal amplio (`dialog_size: extra-large` + SCSS); formulario con sheet y campos distribuidos.
- Eliminado CSS que estrechaba el chatter lateral.
### Added
- Campo **Aplica garantía** en el wizard; al desactivar limpia la línea.
- Tests E2E cotización→factura y factura directa con wizard.

## [19.0.1.6.0] - 2026-07-09
### Added
- Wizard **Configurar garantía** por línea (`justech.warranty.line.config.wizard`):
  meses, tipo y observaciones en modal; sin columnas permanentes en la grilla.
- Campo **resumen compacto** (`warranty_summary`), p. ej. `12m · Estándar`.
- Campo **condiciones** (`warranty_notes`) en línea; se transfiere a la garantía real.
### Changed
- Cotización/factura: solo columna **Gar.** (toggle) + resumen + icono ⚙ configurar.
- Eliminadas columnas permanentes de Meses y Tipo en listas de líneas.
- Widget JS `warranty_config_button` + auto-apertura wizard al activar toggle.

## [19.0.1.5.0] - 2026-07-09
### Changed
- Columnas de garantía en cotización/factura **compactas** (al final de la línea,
  anchos fijos, SCSS) para evitar scroll horizontal.
- Etiquetas de lista: **Garantía**, **Meses**, **Tipo**; Meses/Tipo solo visibles
  cuando Garantía está activa.

## [19.0.1.4.0] - 2026-07-08
### Added
- **Garantía en cotización/pedido** (`sale.order.line`): Garantía, Meses y Tipo;
  autocompletado desde producto; editable antes de confirmar; se transfiere a la
  factura al facturar (sin crear registro de garantía hasta postear la factura).
- Vistas de Garantías ampliadas: filtros y agrupación por **cliente**, **factura**,
  **producto**, **estado**, **pendiente de serie** y **vencimiento** (mes).
### Changed
- Líneas de factura y cotización: columna **Garantía** siempre visible; **Meses** y
  **Tipo** solo cuando Garantía está activada (`invisible="not warranty_apply"`).
- La factura hereda la condición de garantía desde la línea de venta vinculada.

## [19.0.1.3.0] - 2026-07-08
### Added
- Nuevo estado **Pendiente de serie** (`pending_serial`): la garantía se crea así cuando
  el producto requiere serie y aún no está registrada (flujo: facturar primero, serie
  después). Al registrar la serie en la garantía, pasa automáticamente a **Activa**.
- Campo calculado `certificate_ready` (lista para certificado PDF en Fase 2): solo
  verdadero cuando la garantía está activa y completa (con serie si aplica).
### Changed
- **Factura simplificada**: por línea solo **Garantía (Sí/No)**, **Meses** y **Tipo**.
  Eliminadas de la línea: fecha inicio, fecha vencimiento y número de serie/lote
  (evita scroll horizontal; fechas y serie viven en el módulo de Garantías).
- Filtro rápido **Pendiente de serie** en búsqueda de garantías; aviso en formulario
  de garantía cuando falta la serie.

## [19.0.1.2.0] - 2026-07-08
### Added
- **Garantía por línea de factura** (`account.move.line`): campos visibles y
  editables por línea — Aplica garantía, Meses, Tipo, Inicio (sugerida),
  Vencimiento (calculado) y Serie/Lote. Se autocompletan desde el producto al
  agregarlo y pueden ajustarse antes de validar la factura.
- Generación **por línea**: al validar se crea una garantía independiente por cada
  línea con garantía (vinculada a `invoice_line_id`); las líneas sin garantía no
  generan nada. Serie sin lote queda en borrador (se asigna en entrega/inventario).
- Nueva pestaña **"Garantías"** en la factura (con nota explicativa y lista de
  garantías generadas) + columnas de garantía dentro de "Líneas de factura".
### Changed
- **Dashboard** convertido en panel operativo: vista **kanban** agrupada por estado
  (+ lista, gráfico y pivote) con filtros rápidos, en lugar del gráfico vacío.
- La generación de garantías ya no depende solo de los meses del producto, sino de
  la configuración de cada línea (permite laptop 12m, monitor 24m, cable sin garantía).

## [19.0.1.1.0] - 2026-07-08
### Added
- **Aplicación independiente** en el launcher principal de Odoo: menú raíz
  "Justech Garantías" con icono corporativo (`web_icon`).
- **Icono profesional** corporativo (fondo azul, "J" blanca y escudo) en
  `static/description/icon.png`.
- Menú **Dashboard** con vistas gráfico/pivote (`view_justech_warranty_graph`,
  `view_justech_warranty_pivot`), preparado para ampliarse en la Fase 2.
- Submenú **Configuración** (solo responsables): Configuración General, Tipos de
  Garantía y Motivos de Reclamo.
- Modelo `justech.warranty.type` (Tipos de Garantía) con catálogo por defecto y
  campo opcional `type_id` en la garantía (onchange que fija clase y meses).
- Modelo `justech.warranty.claim.reason` (Motivos de Reclamo) con catálogo por
  defecto y campo opcional `reason_id` en el reclamo.
- Ajustes en **Configuración → Ajustes** (`res.config.settings`): términos de
  garantía por defecto y días de aviso de vencimiento (por compañía).
- Términos por defecto aplicados automáticamente a garantías nuevas sin términos.
- Página profesional de Apps (`static/description/index.html`) con objetivo,
  funcionalidades, integraciones y capturas.
### Changed
- Descripción de plantilla eliminada; `__manifest__.py` con descripción y
  `summary` profesionales.

## [19.0.1.0.2] - 2026-07-08
### Added
- Smart button **Garantías** en el formulario de factura (`account.move`), que
  enlaza a las garantías generadas desde esa factura (`views/account_move_views.xml`).
### Changed
- Campo `warranty_months` reubicado a la pestaña **Información general** del
  producto (junto a Categoría), con etiqueta visible, en lugar de la fila de
  casillas superior. Detectado al preparar evidencias visuales.

## [19.0.1.0.1] - 2026-07-08
### Changed
- `action_activate` valida la serie de forma **atómica** (lanza `ValidationError`
  inmediato si el producto se rastrea por serie y no hay lote), en vez de depender
  del `@api.constrains` en el flush. El constraint se mantiene como red de seguridad.
  Detectado durante la validación funcional en `justech_lab`/`justech_dev`.

## [19.0.1.0.0] - 2026-07-08
### Added
- Modelo `justech.warranty` (garantía) con vigencia calculada, estados y secuencia `GAR/AÑO/#####`.
- Modelo `justech.warranty.claim` (RMA) con flujo de estados y secuencia `RMA/AÑO/#####`.
- Campo `warranty_months` en `product.template`.
- Generación automática de garantías al validar la factura de cliente (`account.move`).
- Obligatoriedad de lote/serie al activar garantías de productos con seguimiento por serie.
- Cron diario para marcar garantías vencidas.
- Grupos de seguridad (Usuario/Responsable) y reglas multi-compañía.
- Vistas (lista, formulario, búsqueda), menús y pruebas unitarias.
