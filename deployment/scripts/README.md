# deployment/scripts/

Scripts operativos de **ejemplo**. No ejecutar en Fase 0.

| Script               | Propósito                                              |
| -------------------- | ------------------------------------------------------ |
| `backup.example.sh`  | Respaldo de base de datos + filestore.                 |
| `deploy.example.sh`  | Flujo de despliegue de referencia (contenedores).      |
| `restore.example.sh` | Restauración desde respaldo (operación destructiva).   |

## Reglas

- **No aprobados para producción.** Los comandos peligrosos están comentados.
- Las credenciales se proveen por variables de entorno / `~/.pgpass`, **nunca**
  hardcodeadas ni commiteadas.
- Requieren completar `.env` a partir de `config/env.example`.
- `restore.example.sh` es **destructivo**: validar siempre el destino.
- Ver estrategia en [`docs/09_BACKUP_AND_ROLLBACK.md`](../../docs/09_BACKUP_AND_ROLLBACK.md).
