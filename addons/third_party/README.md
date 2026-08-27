# addons/third_party

Módulos **externos aprobados** (de terceros / comunidad OCA u otros).

## Regla fundamental

**Nunca** se debe modificar directamente un módulo de terceros sin documentarlo.
Cada módulo incorporado aquí debe registrar, como mínimo, la siguiente ficha:

| Campo                     | Descripción                                             |
| ------------------------- | ------------------------------------------------------- |
| Fuente                    | Origen del módulo (OCA, autor, marketplace, etc.)       |
| Licencia                  | Licencia original del módulo                             |
| Versión                   | Versión exacta incorporada                               |
| Repositorio original      | URL del repositorio de origen                            |
| Motivo de uso             | Por qué se incorpora al proyecto                         |
| Cambios locales           | Lista de modificaciones locales (idealmente ninguna)    |
| Estrategia de actualización | Cómo se mantendrá actualizado frente al upstream      |

## Reglas

- Respetar siempre la licencia original de cada módulo de terceros.
- Preferir *no* modificar; si es imprescindible, aislar los cambios en un módulo
  puente con prefijo `justech_` en lugar de editar el módulo de terceros.
- No incorporar código con licencia incompatible (ver [`LICENSE`](../../LICENSE)).
- No incluir credenciales, datos productivos ni información de clientes.
- Compatibilidad con **Odoo 19** obligatoria antes de aprobar.

## Estado

`Fase 0 — Vacío por diseño. Pendiente de selección y aprobación de terceros.`

## justgroup_prod_source/

Snapshot code-only from Justgroup PROD (2026-08-27). See `justgroup_prod_source/README.md` and `docs/migration/JUSTGROUP_MODULE_CLASSIFICATION.md`.
