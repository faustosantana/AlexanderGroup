# Doralex — Enterprise staging

Clon técnico de la base Community de producción para convertir a Odoo 19
Enterprise **sin tocar** `doralexgroup.cloud`.

## Aislamiento

| Recurso | Valor |
| --- | --- |
| Red | `doralex_ent_staging_net` |
| Volúmenes | `doralex_ent_staging_db_data`, `doralex_ent_staging_odoo_data` |
| DB | `doralex_ent_staging` |
| Loopback | `127.0.0.1:8269` / `8272` |
| Enterprise addons | `./enterprise-addons` (no `/opt/doralex/enterprise`) |
| Imagen Wave 2 | `doralex-odoo-enterprise:19` (derivada de `odoo:19` + `.deb` oficial) |

## Flujo

1. `bash scripts/backup.sh production`
2. `CONFIRM=yes bash scripts/clone_prod_to_enterprise_staging.sh <backup_dir>`
3. Depositar `odoo_19.0+e.*_all.deb` en `/opt/doralex/secrets/odoo_enterprise/archive/`
   (descarga: odoo.com → Odoo 19 → Ubuntu • Debian → Enterprise).
4. `CONFIRM=yes bash scripts/convert_community_to_enterprise.sh`
   (valida el `.deb`, construye la imagen derivada, `-i web_enterprise`, nunca `-u all`)
5. Waves de módulos: `CONFIRM=yes bash scripts/install_enterprise_waves.sh <wave>`

GitHub no es requisito. Cutover: **no** hasta aprobación explícita.
