# Doralex — Estado de fase (Golden DEV) — corregido

> Fecha: 2026-08-27. `JUSTGROUP = SOURCE READ-ONLY`, `DORALEX = TARGET`
> (`2.25.121.111` = **solo** Doralex). PROD sin cambios funcionales.

## Estado actual (verificado)

| Clave | Valor |
| ----- | ----- |
| DORALEX_DEV_DNS | **PASS** (`dev.doralexgroup.cloud` → `2.25.121.111`) |
| DORALEX_DEV_SSL | **PASS** (Let's Encrypt, exp. 2026-11-25, auto-renovación) |
| DORALEX_DEV_HTTPS | **PASS** (`https://dev.doralexgroup.cloud`, HTTP→HTTPS 301) |
| DORALEX_DEV_HEALTH | **PASS** (`/web/health` 200) |
| DORALEX_DEV_RUNTIME_ERRORS | **0** |
| DORALEX_DEV_TESTS | **9/9** (golden env, datos temporales revertidos) |
| REPO_TESTS | **15/15** (pytest) |
| MULTICOMPANY_SCAN | **PASS** (aislamiento `company_id`, 96 record rules) |
| HARDCODE_SCAN | **PASS** (`custom-addons` vacío) |
| DORALEX_PROD_BACKUP | **PASS** (verificado, SHA256) |
| DORALEX_DEV_BACKUP | **PASS** (`dev_20260827_163526`) |
| JUSTGROUP_AUDIT | **PARTIAL** (versión/edición confirmadas; inventario de módulos pendiente) |
| MODULE_CLASSIFICATION | **PASS** (estándar/Enterprise/custom conocidos clasificados) |
| CUSTOM_MODULE_MIGRATION | **PARTIAL** (0 módulos custom copiados — falta código fuente) |
| ENTERPRISE_STATUS | Justgroup=Enterprise `19.0+e-20260324`; Doralex=Community → `BLOCKED_BY_ENTERPRISE_SOURCE` |
| ENTERPRISE_DECISION | **DONE** (ver `ENTERPRISE_DECISION.md`) |
| DORALEX_6_COMPANIES_READY | **YES** (capacidad validada 6/6, sin crear empresas reales) |
| READY_FOR_STANDARD_DATA_LOAD | **YES** |
| READY_FOR_FULL_DORALEX_DATA_LOAD | **PENDING_JUSTGROUP_MODULE_AUDIT** |

> **No** se marca `READY_FOR_DORALEX_DATA_LOAD = YES` mientras `JUSTGROUP_AUDIT` y
> `CUSTOM_MODULE_MIGRATION` sigan `PARTIAL`.

## Bloqueos reales restantes

### 1. DNS + SSL dev — RESUELTO (2026-08-27)

`dev.doralexgroup.cloud` → `2.25.121.111` (DNS Hostinger creado por el usuario) y
**SSL emitido** con Let's Encrypt (`certbot --nginx --redirect`):

- Certificado: emisor **Let's Encrypt** (CN `dev.doralexgroup.cloud`), exp. **2026-11-25**.
- `https://dev.doralexgroup.cloud/web/health` → **200**; `ssl_verify_result=0` (cadena válida).
- HTTP→HTTPS **301** (sin loops); `X-Forwarded-Proto`/`X-Forwarded-For` y websocket (`:8172`) configurados.
- Renovación automática: `certbot.timer` (systemd) activo.

### 2. Inventario real de módulos de Justgroup

Para pasar `JUSTGROUP_AUDIT` de `PARTIAL` → completo y habilitar
`CUSTOM_MODULE_MIGRATION`, se requiere acceso **de solo lectura** a `erp.justech.do`:
admin de Odoo (para leer `ir.module.module`, ACL, record rules, cron, QWeb, Studio),
o SSH a su servidor, o un export de `ir.module.module` + `custom-addons`. **No inventar
módulos.** Sin ese acceso no se copia ni adapta código custom de Justech.

## Congelamiento (Golden DEV)

Se mantiene este entorno como **Golden DEV** hasta resolver el DNS de dev y el
inventario real de Justgroup: DEV estable, PROD intacto, backups verificados,
evidencia conservada en `docs/migration/evidence/`.
