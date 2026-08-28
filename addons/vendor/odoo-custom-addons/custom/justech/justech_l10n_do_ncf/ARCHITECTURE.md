# Arquitectura — justech_l10n_do_ncf

## Propósito

Gestión de rangos NCF, asignación automática al publicar, validación de duplicados
y trazabilidad de consumo — producto Justech desacoplado de implementaciones cliente.

## Capas

| Capa | Ubicación | Responsabilidad |
|------|-----------|-----------------|
| **Services** | `services/` | Resolver tipo doc, duplicados, reglas Adel, asignación pre-post |
| **Validators** | `validators/` | Alcance duplicados v2.0, reglas B14/250k/B16 |
| **Models** | `models/` | `account.move`, `ncf.range`, `ncf.consumption`, `ncf.admin.center`, `sale.order` |

## Servicios

| Modelo | Rol |
|--------|-----|
| `justech.do.ncf.document.type.resolver.service` | Resuelve B01/B02/B04/B11… según move_type |
| `justech.do.ncf.duplicate.service` | Valida NCF manual + unicidad posted (v2.0 Python) |
| `justech.do.ncf.business.rules.service` | B14 sin ITBIS, RD$250k+RNC, B16 exportaciones |
| `justech.do.ncf.assignment.service` | Orquesta locks, rangos, reglas y consumo |
| `justech.do.ncf.range.audit.service` | Resumen de uso de rangos |
| `justech.do.ncf.diagnostic.service` | Escaneo read-only de inconsistencias |

## Flujo de asignación (sin cambio funcional Sprint 1)

```mermaid
sequenceDiagram
    participant AM as account.move
    participant AS as ncf.assignment.service
    participant RS as document.type.resolver
    participant NR as ncf.range
    participant DS as ncf.duplicate.service

    AM->>AS: _post(soft)
    AS->>RS: resolve_for_move / should_auto_assign
    alt NCF manual
        AS->>DS: validate_manual_ncf
    else Auto-assign
        AS->>NR: _find_active_range_for_update
        NR->>NR: consume_next
    end
    AM->>AM: super()._post()
```

## Delegación desde modelos

`account.move._justech_*` conserva la API interna existente pero delega en servicios.
Tests en `tests/test_justech_l10n_do_ncf.py` garantizan regresión cero.

## Dependencias

```
justech_l10n_do_base, account_debit_note, sale
```

## Diagramas

- `diagrams/architecture.mmd`
- `diagrams/dependencies.mmd`
