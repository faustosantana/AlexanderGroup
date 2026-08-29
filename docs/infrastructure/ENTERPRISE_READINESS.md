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

## Paquete a depositar

1. https://www.odoo.com/page/download (sesión de la suscripción Doralex)
2. **Odoo 19 → Ubuntu • Debian → Enterprise → Download**
3. Archivo: `odoo_19.0+e.*_all.deb` (no Community, no nightly)
4. Ruta: `/opt/doralex/secrets/odoo_enterprise/archive/`
5. `CONFIRM=yes bash /opt/doralex/scripts/convert_community_to_enterprise.sh`

Detalle vivo: [`../enterprise_conversion/STATUS.md`](../enterprise_conversion/STATUS.md).
