# Conversión Community → Enterprise — estado

**Fecha:** 2026-08-29  
**Cutover:** `CUTOVER_ALLOWED = NO` (detenerse hasta aprobación).  
**Justgroup:** solo lectura. Transacciones Justgroup: no copiadas.

```
COMMUNITY_TO_ENTERPRISE = IN_PROGRESS (staging clonado; Wave 2 espera .deb)
ENTERPRISE_PACKAGE_ROUTE = PRIMARY
GITHUB_BLOCKER = REMOVE
ODOO_ENTERPRISE             = NO   (falta el .deb oficial en el drop-path)
WEB_ENTERPRISE              = NO
ENTERPRISE_SOURCE           = PENDING_OFFICIAL_PACKAGE
DORALEX_REPORTS_PRESERVED   = YES  (19.0.3.8.5 / 58 QWeb)
DORALEX_DATA_PRESERVED      = YES
JUSTGROUP_TRANSACTIONS_COPIED = NO
CUSTOM_MODULES_ALIGNED      = NO
SPANISH_UI                  = NO
QA_COMPLETE                 = NO
PROD_TOUCHED                = NO
CUTOVER_ALLOWED             = NO
```

Staging loopback: `http://127.0.0.1:8269` (`{"status":"pass"}`).  
Versión staging = `19.0-20260817` Community (idéntica a Prod).  
Justgroup (solo lectura) = `19.0+e-20260324`.  
Host y contenedor staging: Ubuntu 24.04, paquete dpkg `odoo 19.0.20260817`.  
DNS no es requisito de Wave 2.

## Waves

| Wave | Qué | Estado |
| --- | --- | --- |
| 0 | Backup Prod completo | PASS `production_20260829_131434` |
| 1 | Clon `enterprise-staging` | PASS (aislado, neutralize mail/cron) |
| 2 | Paquete oficial Enterprise + `web_enterprise` | **PENDING_OFFICIAL_PACKAGE** (drop-path vacío; GitHub no es bloqueo) |
| 3 | Apps Enterprise | pendiente Wave 2 |
| 4 | Community faltantes | pendiente Wave 2 |
| 5 | Custom Justech aplicables | pendiente revisión de identidad |
| 6 | Reportes Doralex | preservar / comparar |
| 7 | Español `es_DO` / `es_ES` | pendiente (no dejarlo para el final) |
| 8 | QA | pendiente |
| Cutover | DNS/proxy a Prod | **NO** |

## Wave 2 — paquete oficial (ruta primaria)

Documentación Odoo 19 *Switch from Community to Enterprise* (Linux installer):
backup → stop → `dpkg -i` del `.deb` Enterprise → `-i web_enterprise --stop-after-init` → restart → código de suscripción.

Este staging es Docker (`odoo:19`). **No** se hace `dpkg` dentro del contenedor vivo ni en el host. Se construye una **imagen staging derivada** (`doralex-odoo-enterprise:19`) que instala el `.deb` oficial sobre la misma base, con los mismos volúmenes/filestore/custom-addons.

GitHub `odoo/enterprise` es vía **secundaria**, no requisito.

Si el servidor no puede descargar porque odoo.com pide login:

1. https://www.odoo.com/page/download
2. **Odoo 19 → Ubuntu • Debian → Enterprise → Download**
3. Archivo: `odoo_19.0+e.*_all.deb` (no Community, no nightly)
4. Colocar en: `/opt/doralex/secrets/odoo_enterprise/archive/`
5. `CONFIRM=yes bash /opt/doralex/scripts/convert_community_to_enterprise.sh`

El aviso estándar de activación de suscripción en staging es aceptable.
Instalable ≠ activado. La suscripción Doralex ya está comprada.

Justgroup no se usa como fuente. Prod no se toca. DNS no es requisito.

## URL staging

- Loopback: `http://127.0.0.1:8269`
- Público previsto: `https://enterprise.doralexgroup.cloud` (hace falta A → `2.25.121.111` + certbot)

## Rollback

1. No hay cutover: Prod sigue en Community `odoo:19`.
2. Staging: `ODOO_IMAGE=odoo:19` y `docker compose up -d`, o down + borrar volúmenes `doralex_ent_staging_*`.
3. Restore Prod solo desde `production_*` backups (doble guarda `ALLOW_PROD`).
