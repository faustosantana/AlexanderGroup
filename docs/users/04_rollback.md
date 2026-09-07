# Backup y rollback de permisos

## Backup de producción (ejecutado)

```
ODOO_USER_BACKUP = PASS
NAME = pre_alexander_users_permissions_20260907_122013
PATH = /opt/doralex/backups/production/production_20260907_122013
verify_backup.sh = BACKUP VALIDO
db.dump SHA256 = 2164e0f0626a93cfd33b6b180849bd22bac5607281a80419fe18db730cc08adc
```

Incluye DB, filestore, config, custom-addons y la matriz
`odoo_user_provision_matrix.json`.

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
