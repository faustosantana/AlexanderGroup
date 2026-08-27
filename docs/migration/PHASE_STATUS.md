# Doralex — Estado de fase (Golden DEV) — corregido

> Fecha: 2026-08-27. `JUSTGROUP = SOURCE READ-ONLY`, `DORALEX = TARGET`
> (`2.25.121.111` = **solo** Doralex). PROD sin cambios funcionales.

## Estado actual (verificado)

| Clave | Valor |
| ----- | ----- |
| DORALEX_DEV_HEALTH | **PASS** (`/web/health` 200) |
| DORALEX_DEV_RUNTIME_ERRORS | **0** |
| DORALEX_DEV_TESTS | **9/9** (golden env, datos temporales revertidos) |
| REPO_TESTS | **15/15** (pytest) |
| MULTICOMPANY_SCAN | **PASS** (aislamiento `company_id`, 96 record rules) |
| HARDCODE_SCAN | **PASS** (`custom-addons` vacío) |
| DORALEX_PROD_BACKUP | **PASS** (verificado, SHA256) |
| DORALEX_DEV_BACKUP | **PASS** (`dev_20260827_163526`) |
| JUSTGROUP_AUDIT | **PARTIAL** (versión confirmada; inventario de módulos pendiente) |
| CUSTOM_MODULE_MIGRATION | **PARTIAL** (0 módulos custom copiados) |
| ENTERPRISE_STATUS | Justgroup=Enterprise `19.0+e-20260324`; Doralex=Community → `BLOCKED_BY_ENTERPRISE_SOURCE` |
| READY_FOR_STANDARD_DATA_LOAD | **YES** |
| READY_FOR_FULL_DORALEX_DATA_LOAD | **PENDING_JUSTGROUP_MODULE_AUDIT** |

> **No** se marca `READY_FOR_DORALEX_DATA_LOAD = YES` mientras `JUSTGROUP_AUDIT` y
> `CUSTOM_MODULE_MIGRATION` sigan `PARTIAL`.

## Bloqueos reales restantes

### 1. DNS dev — paso manual exacto (no hay API de Hostinger en el entorno)

`doralexgroup.cloud` está en **Hostinger** (NS `*.dns-parking.com`). No hay token
de API en el entorno, por lo que se documenta el paso manual (no bloquea el resto):

1. Entrar a **hPanel de Hostinger** → *Dominios* → `doralexgroup.cloud` → **Zona DNS / DNS Records**.
2. **Añadir registro**:
   - **Tipo:** `A`
   - **Nombre / Host:** `dev`
   - **Apunta a / Points to:** `2.25.121.111`
   - **TTL:** por defecto (300–3600).
3. Guardar y esperar propagación. Validar: `dig +short dev.doralexgroup.cloud` → `2.25.121.111`.

En cuanto resuelva, el SSL de dev se emite **automáticamente**
(`certbot --nginx -d dev.doralexgroup.cloud --redirect`); el vhost `:80` de dev ya
está configurado en Nginx.

> Alternativa: cargar un `HOSTINGER_API_TOKEN` como Secret para crearlo por API.

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
