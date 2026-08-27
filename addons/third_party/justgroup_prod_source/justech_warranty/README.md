# Justech Garantías (`justech_warranty`)

Gestión del ciclo de vida de garantías de productos y reclamos (RMA) para el ERP Justgroup (Odoo 19).

## Funcionalidad
- Registro de garantías con vigencia calculada (`fecha inicio + meses`).
- Duración por producto mediante `warranty_months` en la ficha de producto.
- Generación automática de garantías al **validar la factura de cliente**.
- Seguimiento por **lote / número de serie** (obligatorio al activar garantías de
  productos con seguimiento por serie).
- **Reclamos / RMA** básicos asociados a cada garantía.
- Cron diario que marca como *vencidas* las garantías activas expiradas.
- Trazabilidad vía `justech_global_audit_log`.

## Estados
- Garantía: `borrador → activa → vencida / reclamada / anulada`.
- Reclamo: `borrador → enviado → en proceso → resuelto / rechazado`.

## Dependencias
`base`, `justech_core`, `product`, `sale`, `account`, `stock`, `justech_global_audit_log`.

## Seguridad
- `Usuario de Garantías`: crear/editar garantías y reclamos.
- `Responsable de Garantías`: además eliminar.
- Reglas multi-compañía sobre garantías y reclamos.

## Instalación / pruebas (entorno dev)
```bash
odoo -c odoo-dev.conf -d justech_lab -i justech_warranty \
     --test-enable --stop-after-init
```

## Versionado
SemVer Odoo: `19.0.MAJOR.MINOR.PATCH`. Ver `CHANGELOG.md`.

## Documentación
- Funcional: `docs/FUNCIONAL.md`
- Técnica: `docs/TECNICO.md`
