# Backup y rollback de permisos

## Antes de producción

Crear backup con `deployment/doralex/scripts/backup.sh production` y
etiquetar el directorio:

`pre_alexander_users_permissions_<timestamp>`

Debe incluir DB, filestore, config, custom addons. Validar con
`verify_backup.sh`. Si falla: STOP.

## Matriz de reversión Odoo

Guardada por el provisionador (`USER_ID`, `OLD_LOGIN`, `NEW_LOGIN`,
`OLD_GROUPS`, `NEW_GROUPS`).

Para revertir solo logins/grupos (sin restaurar DB):

1. Alexander uid 5: `login = inversionesdoralex@gmail.com` y grupos
   previos (Invoicing + Inventory User + Purchase User + Sales All
   Documents). Quitar Settings si se añadió en este cambio.
2. Archivar (no borrar) los 5 usuarios nuevos.

Restaurar el backup completo solo si hay daño estructural. No se tocan
facturas históricas, NCF ni apertura en el rollback de usuarios.
