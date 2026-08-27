# Hotfix catálogo fiscal compartido (19.0.1.23.0)

## Causa AccessError

| Pieza | Valor |
|-------|--------|
| Modelo | `justech.do.fiscal.document.type` |
| Datos | 11 tipos B01–B17 con `company_id = JUSTECH` |
| Regla | `Fiscal Document Type: multi-company` → `company_id = False OR company_id in company_ids` |
| Gatillo | Usuario en Omni (u otra filial) con switcher sin JUSTECH; resolver/M2O lee tipo B14 de JUSTECH |

## Corrección

- Migración: `company_id = NULL` en tipos DGII (catálogo compartido).
- Default modelo: `company_id=False`.
- Constraint: `unique(prefix)`.
- ACL lectura para vendedores (`sales_team.group_sale_salesman`).

## No cambia

- Rangos NCF, secuencias, consumo (siguen por empresa).
- Facturas, NCF emitidos, montos.
