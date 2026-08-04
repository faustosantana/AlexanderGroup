# migrations/

Espacio reservado para **notas y scripts de migración** de datos y de versiones de
módulos (Fase 9 y actualizaciones futuras).

## Estado

`Fase 0 — Vacío por diseño.` Aún no hay migraciones porque no existen módulos ni
datos.

## Alcance futuro

- Scripts de migración de datos maestros (clientes, proveedores, productos).
- Saldos iniciales y documentos abiertos.
- Migraciones de esquema entre versiones de módulos (`19.0.x.y.z`).
- Notas de compatibilidad al actualizar Odoo.

## Reglas

- **Nunca** incluir datos reales, dumps (`*.sql`, `*.dump`) ni respaldos aquí; van
  fuera de Git (ver [`../SECURITY.md`](../SECURITY.md)).
- Documentar cada migración: origen, destino, pasos, reversión (rollback).
- Probar toda migración en TEST antes de PROD (ver
  [`../docs/09_BACKUP_AND_ROLLBACK.md`](../docs/09_BACKUP_AND_ROLLBACK.md)).
