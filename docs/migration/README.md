# docs/migration/ — Migración desde Justgroup (futuro)

Espacio para la **auditoría y migración controlada** de módulos del entorno
Justgroup hacia Doralex. **No** se copia nada a ciegas.

## Reglas

- **No** copiar todavía todos los módulos de Justgroup.
- **No** copiar la base de datos de Justgroup como base de Doralex.
- **No** copiar datos empresariales de Justgroup.
- Solo se reutiliza, **tras auditoría**: código, módulos, arquitectura y mejoras
  compatibles.

## Proceso

1. Auditar Justgroup y producir el inventario:
   [`JUSTGROUP_MODULE_INVENTORY.md`](JUSTGROUP_MODULE_INVENTORY.md).
2. Clasificar cada módulo: `REQUIRED` / `OPTIONAL` / `NOT_APPLICABLE` /
   `REQUIRES_ADAPTATION` / `BLOCKED`.
3. Migrar solo lo clasificado y aprobado, primero a **Dev**, con pruebas.

Auditoría de stack 2026-08-29 (Justgroup Enterprise vs Doralex Community):
[`../stack_audit/JUSTGROUP_DORALEX_STACK_AUDIT.md`](../stack_audit/JUSTGROUP_DORALEX_STACK_AUDIT.md).

Relacionado: [`../05_REUSE_ASSESSMENT.md`](../05_REUSE_ASSESSMENT.md) y
[`../04_MODULE_INVENTORY.md`](../04_MODULE_INVENTORY.md).
