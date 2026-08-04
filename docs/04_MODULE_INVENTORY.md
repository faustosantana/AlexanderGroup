# 04 — Inventario de Módulos

> **Inventario preparado pero vacío.** Se completa durante la auditoría de
> Justgroup (Fase 2). No copiar módulos hasta aprobarlos.

## Tabla de inventario

| Módulo | Repositorio origen | Versión | Dependencias | Tipo | Estado | Decisión | Observaciones |
| ------ | ------------------ | ------: | ------------ | ---- | ------ | -------- | ------------- |
|        |                    |         |              |      |        |          |               |

## Valores permitidos

### `Tipo`
- Estándar Odoo.
- Enterprise.
- Justech compartido.
- Justech específico.
- Tercero.
- Alexander específico.

### `Decisión`
- Reutilizar sin cambios.
- Reutilizar con adaptación.
- Reescribir.
- Sustituir.
- No utilizar.
- Pendiente de análisis.

## Notas

- El campo `Estado` refleja el avance del análisis (p. ej. Pendiente / En revisión
  / Aprobado / Rechazado).
- Cada módulo evaluado debe enlazar su ficha de evaluación en
  [`05_REUSE_ASSESSMENT.md`](05_REUSE_ASSESSMENT.md).
- Los módulos de terceros deben documentar fuente, licencia y versión (ver
  `addons/third_party/README.md`).
