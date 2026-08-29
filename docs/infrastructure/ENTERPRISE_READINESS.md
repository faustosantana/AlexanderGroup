# Odoo 19 Enterprise — Estado de disponibilidad

## Objetivo

Convertir **Doralex Community → Enterprise** en `DORALEX_ENTERPRISE_STAGING`
con el **paquete oficial** Odoo 19 (cuenta/suscripción Doralex).  
Prod (`doralexgroup.cloud`) no se toca. `CUTOVER_ALLOWED = NO`.

## Estado: `ENTERPRISE_PACKAGE_ROUTE = PRIMARY`

- Suscripción Enterprise Doralex: **comprada**.
- Activación del código: **después** de instalar `web_enterprise` (no bloquea).
- GitHub `odoo/enterprise`: **no es requisito** (`GITHUB_BLOCKER = REMOVE`).
- Staging corre Docker `odoo:19` (Ubuntu 24.04, dpkg `odoo`). El `.deb` oficial
  se instala en una **imagen derivada** `doralex-odoo-enterprise:19`, no con
  `dpkg` ad-hoc en el contenedor vivo ni en el host.

Arquitectura de paths (sin cambiar):

- `addons_path` = `/mnt/enterprise,/mnt/custom-addons`
- `/opt/doralex/enterprise` lo monta **Prod Community**: no escribir Enterprise ahí.
- Drop-path del instalador: `/opt/doralex/secrets/odoo_enterprise/archive/`

## Desbloqueo de la descarga automática

El instalador oficial no pide login de GitHub. Pide el **código de contrato**
y el servidor baja el `.deb` (`deb_19e`).

1. Escribir el código (una línea) en
   `/opt/doralex/secrets/odoo_enterprise/subscription_code` (`chmod 600`)
2. `bash /opt/doralex/scripts/download_odoo_enterprise.sh`
3. `CONFIRM=yes bash /opt/doralex/scripts/convert_community_to_enterprise.sh`

No subir el `.deb` a mano. No usar nightly/Community. Prod no se toca.

Detalle vivo: [`../enterprise_conversion/STATUS.md`](../enterprise_conversion/STATUS.md).
