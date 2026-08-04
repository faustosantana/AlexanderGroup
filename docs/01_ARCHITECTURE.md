# 01 — Arquitectura

> Documento vivo. La arquitectura definitiva depende del levantamiento (Fase 1) y
> de la infraestructura (Fase 3). Aquí se describe la arquitectura **objetivo** de
> alto nivel y las decisiones preliminares.

## Componentes objetivo

| Componente     | Descripción                                           | Estado     |
| -------------- | ----------------------------------------------------- | ---------- |
| Odoo 19        | ERP (Community o Enterprise por confirmar)            | Por definir |
| PostgreSQL     | Base de datos relacional                              | Por definir |
| Nginx          | Proxy inverso + TLS                                   | Por definir |
| Docker         | Empaquetado y orquestación de servicios               | Por definir |
| Almacenamiento | Filestore + backups (fuera de Git)                    | Por definir |

## Diagrama lógico (alto nivel)

```text
        Internet
           |
        [ Nginx ]  (TLS, proxy inverso)  -- deployment/nginx
           |
        [ Odoo 19 ]  (workers, cron)     -- addons/{third_party,shared,alexander}
           |
      [ PostgreSQL ]                      -- volumen persistente
           |
   [ Filestore / Backups ]  (NUNCA en Git)
```

## Organización de addons

Orden sugerido en `addons_path` (de menor a mayor especificidad):

1. `addons/third_party` — módulos externos aprobados.
2. `addons/shared` — módulos reutilizables Justech auditados (`justech_*`).
3. `addons/alexander` — módulos específicos del grupo (`justech_alexander_*`).

## Multiempresa

- Seis compañías bajo una misma instancia (por confirmar en levantamiento).
- Procesos compartidos y separados (ver [`03_COMPANY_MATRIX.md`](03_COMPANY_MATRIX.md)).
- Intercompañía: ventas, compras, transferencias y consolidación (Fase 7).
- Reglas de registro (record rules) por compañía y mínimo privilegio
  (ver [`06_SECURITY_MODEL.md`](06_SECURITY_MODEL.md)).

## Ambientes

DEV / TEST / PROD (ver [`14_ENVIRONMENT_MATRIX.md`](14_ENVIRONMENT_MATRIX.md)).

## Decisiones abiertas

- Community vs. Enterprise.
- Una instancia multiempresa vs. instancias separadas.
- Estrategia de facturación electrónica / NCF.
- Consolidación contable.

Registrar cada decisión en [`13_DECISION_LOG.md`](13_DECISION_LOG.md).
