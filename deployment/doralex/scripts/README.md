# deployment/doralex/scripts/

Scripts de infraestructura para Doralex. Todos usan `lib.sh`, no contienen
secretos y leen la configuración sensible desde el `.env` del entorno.

| Script                  | Qué hace | ¿Requiere servidor/Docker? |
| ----------------------- | -------- | -------------------------- |
| `lib.sh`                | Funciones comunes (se importa). | — |
| `setup_ssh_local.sh`    | **En TU máquina**: crea llave dedicada, la instala en el servidor y configura alias SSH. | Local + red |
| `cloud_ssh_bootstrap.sh`| **En el Cloud Agent**: configura SSH desde el Secret `DORALEX_SSH_PRIVATE_KEY`. | Cloud Agent |
| `audit_server.sh`       | Auditoría **solo lectura** del servidor → Markdown. | SSH (tras autorización) |
| `bootstrap_dirs.sh`     | Crea `/opt/doralex/**` (enterprise-ready) con permisos. No instala nada. | Servidor |
| `render_config.sh`      | Genera `config/odoo.conf` desde `.example` + `.env` (600). | Servidor |
| `backup.sh`             | Backup DB+filestore+config+addons+metadata y **verifica**. | Servidor + Docker |
| `verify_backup.sh`      | Valida un backup: archivos, tamaño>0, checksum SHA256. | Servidor |
| `restore.sh`            | Restore destructivo (guardas `CONFIRM`/`ALLOW_PROD`). | Servidor + Docker |
| `healthcheck.sh`        | Salud de contenedores + HTTP de Odoo en loopback. | Servidor + Docker |
| `validate_isolation.sh` | Verifica aislamiento Prod/Dev y no-exposición de DB. | Servidor + Docker |

## Uso típico (en el servidor, tras la auditoría)

```bash
sudo bash bootstrap_dirs.sh
# copiar release del repo a /opt/doralex/<env>, crear .env, luego:
bash render_config.sh production
DORALEX_BASE=/opt/doralex bash healthcheck.sh production
bash validate_isolation.sh
bash backup.sh production
```

## Convenciones

- `ENV` válido: `production`, `dev` o `enterprise-staging`.
- Runtime Justgroup → staging: `transfer_justgroup_runtime_export.sh`,
  `import_justgroup_runtime_export.sh`, `build_doralex_enterprise_image.sh`,
  `apply_enterprise_runtime_staging.sh`. Hash fijo
  `d406ccfd73225db88b83dfd07def618b2c48e1b1aeaebcc5877f76fa26b4cb86`.
  Nunca `-u all`. Nunca cutover. Nunca Prod.
- Variable `DORALEX_BASE` (por defecto `/opt/doralex`) permite pruebas en otra ruta.
- Ningún script publica PostgreSQL ni imprime secretos.
