# Inventario de módulos Justgroup (para migración)

> **PENDING_AUDIT.** Plantilla vacía. Se completa auditando el entorno Justgroup
> (fase posterior). **No** copiar módulos a ciegas. **No** inventar datos.

## Alcance de la auditoría

Para el Justgroup a auditar, inventariar:

- módulos estándar instalados
- Enterprise
- OCA
- custom addons
- versión exacta
- dependencias
- módulos activos
- módulos no usados
- configuración específica
- cron
- reports
- QWeb
- customizaciones de Studio
- automated actions
- server actions

## Clasificación (valores permitidos)

| Valor                 | Significado |
| --------------------- | ----------- |
| `REQUIRED`            | Necesario para Doralex; migrar. |
| `OPTIONAL`            | Útil pero no imprescindible. |
| `NOT_APPLICABLE`      | No aplica a Doralex. |
| `REQUIRES_ADAPTATION` | Reutilizable con cambios (prefijo `justech_`, quitar refs específicas). |
| `BLOCKED`             | Bloqueado (licencia, dependencia, incompatibilidad 19). |

## Inventario

| Módulo | Origen (repo) | Versión | Tipo (Estándar/Enterprise/OCA/Custom) | Dependencias | ¿Activo? | Cron/Reports/QWeb/Studio/Actions | Clasificación | Observaciones |
| ------ | ------------- | ------: | ------------------------------------- | ------------ | -------- | -------------------------------- | ------------- | ------------- |
|        |               |         |                                       |              |          |                                  |               |               |

## Resumen por clasificación

| Clasificación | Cantidad |
| ------------- | -------: |
| REQUIRED | 0 |
| OPTIONAL | 0 |
| NOT_APPLICABLE | 0 |
| REQUIRES_ADAPTATION | 0 |
| BLOCKED | 0 |

_Pendiente de auditoría._
