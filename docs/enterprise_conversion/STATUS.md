# Conversión Community → Enterprise — estado

**Fecha:** 2026-08-29  
**Cutover:** `CUTOVER_ALLOWED = NO` (detenerse hasta aprobación).  
**Justgroup:** solo lectura. Transacciones Justgroup: no copiadas.

```
COMMUNITY_TO_ENTERPRISE     = IN_PROGRESS (ruta nativa; staging clonado)
ODOO_ENTERPRISE             = NO   (falta fuente odoo/enterprise)
WEB_ENTERPRISE              = NO
ENTERPRISE_SOURCE           = PENDING_OFFICIAL_PACKAGE
DORALEX_REPORTS_PRESERVED   = YES  (check_staging_reports.sh PASS: 19.0.3.8.5 / 58)
DORALEX_DATA_PRESERVED      = YES  (106 módulos, misma DB que Prod)
JUSTGROUP_TRANSACTIONS_COPIED = NO
CUSTOM_MODULES_ALIGNED      = NO
SPANISH_UI                  = NO
QA_COMPLETE                 = NO
```

Staging loopback: `http://127.0.0.1:8269` (`{"status":"pass"}`).  
Versión staging = `19.0-20260817` Community (idéntica a Prod).  
Justgroup (solo lectura) = `19.0+e-20260324`.

## Waves

| Wave | Qué | Estado |
| --- | --- | --- |
| 0 | Backup Prod completo | PASS `production_20260829_131434` |
| 1 | Clon `enterprise-staging` | PASS (aislado, neutralize mail/cron) |
| 2 | Fuente Enterprise + `web_enterprise` | **PENDING_OFFICIAL_PACKAGE** (git 404 + sin ZIP en drop-path) |
| 3 | Apps Enterprise | pendiente Wave 2 |
| 4 | Community faltantes | pendiente Wave 2 |
| 5 | Custom Justech aplicables | pendiente revisión de identidad |
| 6 | Reportes Doralex | preservar / comparar |
| 7 | Español `es_DO` / `es_ES` | pendiente |
| 8 | QA | pendiente |
| Cutover | DNS/proxy a Prod | **NO** |

## Wave 2 — fuente oficial (dos vías)

Comprobado en este agente:

- GitHub `odoo/enterprise` → 404 (la App/token de este entorno no está
  invitada al repo privado).
- Nightly público `nightly.odoo.com/19.0` → solo Community (0 paquetes `+e`).
- No hay ZIP/tarball oficial en el servidor.
- No hay sesión odoo.com / `.netrc` / drop-path.

El proyecto **no** está cerrado: `fetch_odoo_enterprise.sh` acepta **A o B**:

1. Credencial de lectura en `/opt/doralex/secrets/odoo_enterprise/github_token`
   (chmod 600; nunca en Git).
2. ZIP/tarball Enterprise 19 del portal odoo.com (login de la suscripción
   Doralex o enlace del correo de compra) en
   `/opt/doralex/secrets/odoo_enterprise/archive/`.

Luego: `bash fetch_odoo_enterprise.sh` y
`CONFIRM=yes bash convert_community_to_enterprise.sh`.

Justgroup no se usa como fuente. Prod no se toca. DNS no es requisito.

## URL staging

- Loopback: `http://127.0.0.1:8269`
- Público previsto: `https://enterprise.doralexgroup.cloud` (hace falta A → `2.25.121.111` + certbot)

## Rollback

1. No hay cutover: Prod sigue en Community `odoo:19`.
2. Staging: `docker compose` down + borrar volúmenes `doralex_ent_staging_*`.
3. Restore Prod solo desde `production_*` backups (doble guarda `ALLOW_PROD`).
