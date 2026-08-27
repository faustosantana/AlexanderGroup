# Justech Security UX — Permisos Justech

Interfaz clara para administrar **grupos reales de Odoo** por módulo.

## Principios

1. `res.groups` + ACL + Record Rules son la única fuente de seguridad.
2. Esta capa **no** crea ACL, rules ni grupos.
3. Sync quirúrgico: un módulo no borra permisos de otro.
4. Capacidades mostradas solo si existe xmlid/grupo real.
5. Sin dependencias Hellenia.

## Pestañas

- **Permisos Justech** — operación normal (multiárea).
- **Permisos Avanzados** — matriz técnica Odoo (Administrador del Sistema).

## Rollback (DEV)

```text
/root/backups/justech_dev/rc-security-ux-final-*/
```

1. Restaurar `justech_security_ux.before.tgz` en addons.
2. `-u justech_security_ux` en `justech_dev`.
3. O restaurar dump `justech_dev.dump` si hace falta.
