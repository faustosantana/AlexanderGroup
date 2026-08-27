# Studio y Reportes PDF — Preparación (enterprise-ready)

Doralex se prepara desde ya para Odoo Studio y para reportes PDF profesionales,
sin instalar módulos Enterprise ausentes hasta disponer del código legítimo.

## Odoo Studio (`web_studio`) — readiness

- `web_studio` es un módulo **Enterprise**: se instalará cuando la fuente
  Enterprise legítima esté disponible (`ENTERPRISE_SOURCE_PENDING=TRUE`).
- La arquitectura ya lo contempla: `addons_path` incluye `/mnt/enterprise`
  (dir presente, vacío hasta la licencia). No habrá que rehacer nada.
- **Uso previsto (en Dev)**: prototipar formularios, listas, kanban, campos,
  pestañas y UX.
- **Regla**: la lógica crítica y las personalizaciones importantes deben quedar
  **versionadas en módulos Git** (`custom-addons`) cuando corresponda, no vivir
  solo en Studio.

## Reportes PDF (QWeb / XML / CSS)

- Los reportes se desarrollan como **módulos custom versionados** en
  `custom-addons` (QWeb + XML + CSS), no dependiendo solo de Studio.
- **Motor PDF**: Odoo usa `wkhtmltopdf` (patched Qt). Se debe **replicar la misma
  versión** que usa Justgroup para evitar diferencias de render. Registrar la
  versión exacta en [`../migration/JUSTGROUP_TECHNICAL_REFERENCE.md`](../migration/JUSTGROUP_TECHNICAL_REFERENCE.md).
- La imagen oficial de Odoo ya incluye un `wkhtmltopdf` compatible; si Justgroup
  usa una versión específica, se fija en la imagen/paquetes.

### Reportes a personalizar (posterior)

facturas, cotizaciones, órdenes de compra, conduces, recibos, estados de cuenta y
otros. Se harán tras el levantamiento, primero en Dev.

## Dependencias Enterprise futuras (marcar, no instalar aún)

`web_studio`, `documents`, `sign`, `spreadsheet`/`dashboard` y nómina/localización
Enterprise: **BLOCKED_BY_ENTERPRISE_SOURCE** hasta contar con la licencia.
