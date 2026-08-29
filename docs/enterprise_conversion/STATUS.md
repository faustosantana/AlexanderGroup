# Conversión Community → Enterprise — estado

**Fecha:** 2026-08-29  
**Cutover:** `CUTOVER_ALLOWED = NO` (detenerse hasta aprobación).  
**Justgroup:** solo lectura. Transacciones Justgroup: no copiadas.

```
COMMUNITY_TO_ENTERPRISE     = IN_PROGRESS (ruta nativa; staging clonado)
ODOO_ENTERPRISE             = NO   (falta fuente odoo/enterprise)
WEB_ENTERPRISE              = NO
DORALEX_REPORTS_PRESERVED   = YES  (19.0.3.8.5 / 58 QWeb en el clon)
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
| 2 | Fuente Enterprise + `web_enterprise` | **BLOQUEADO** sin acceso a `odoo/enterprise` |
| 3 | Apps Enterprise | pendiente Wave 2 |
| 4 | Community faltantes | pendiente Wave 2 |
| 5 | Custom Justech aplicables | pendiente revisión de identidad |
| 6 | Reportes Doralex | preservar / comparar |
| 7 | Español `es_DO` / `es_ES` | pendiente |
| 8 | QA | pendiente |
| Cutover | DNS/proxy a Prod | **NO** |

## Bloqueador Wave 2

La suscripción Odoo Enterprise **no publica** los addons. Hay que clonar el repo
privado `github.com/odoo/enterprise` (rama `19.0`) con una cuenta GitHub
**vinculada** a la suscripción Doralex en odoo.com.

Este agente no tiene ese token. Justgroup no se usa como fuente (licencia
por instancia).

Colocar el token en el servidor:

```text
/opt/doralex/secrets/odoo_enterprise/github_token
```

o exporte la variable `ODOO_ENTERPRISE_GITHUB_TOKEN` y corra:

`bash /opt/doralex/scripts/fetch_odoo_enterprise.sh`

Luego: `CONFIRM=yes bash convert_community_to_enterprise.sh`

## URL staging

- Loopback: `http://127.0.0.1:8269`
- Público previsto: `https://enterprise.doralexgroup.cloud` (hace falta A → `2.25.121.111` + certbot)

## Rollback

1. No hay cutover: Prod sigue en Community `odoo:19`.
2. Staging: `docker compose` down + borrar volúmenes `doralex_ent_staging_*`.
3. Restore Prod solo desde `production_*` backups (doble guarda `ALLOW_PROD`).
