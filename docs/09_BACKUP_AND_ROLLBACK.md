# 09 — Backups y Rollback

> Estrategia a definir/probar en Fase 3. Aquí se establecen los lineamientos.

## Alcance del respaldo

- **Base de datos** PostgreSQL (por empresa/instancia).
- **Filestore** de Odoo (adjuntos, documentos).
- **Configuración** (plantillas, sin secretos reales).

> ⚠️ Los respaldos, dumps y filestore **nunca** se almacenan en Git
> (ver `.gitignore` y [`../SECURITY.md`](../SECURITY.md)).

## Lineamientos

| Aspecto            | Definición (pendiente de confirmar)                 |
| ------------------ | --------------------------------------------------- |
| Frecuencia         | _Pendiente_ (p. ej. diaria completa + incremental)  |
| Retención          | _Pendiente_                                         |
| Cifrado            | _Pendiente_ (en reposo y en tránsito)               |
| Ubicación          | _Pendiente_ (fuera del servidor productivo)         |
| Prueba de restauración | _Pendiente_ (periódica y documentada)           |

## Scripts de referencia

- `deployment/scripts/backup.example.sh`
- `deployment/scripts/restore.example.sh`

Ambos son ejemplos con comandos peligrosos comentados. No ejecutar en Fase 0.

## Rollback

Estrategia de reversión ante un despliegue o migración fallida:

1. Detener el servicio afectado.
2. Restaurar la última copia válida (DB + filestore).
3. Revertir la versión de código (rama/imagen anterior).
4. Validar funcionalmente.
5. Registrar el incidente en [`12_RISK_REGISTER.md`](12_RISK_REGISTER.md) y
   [`13_DECISION_LOG.md`](13_DECISION_LOG.md).

## Criterios de salida (Go/No-Go) para producción

- Backup reciente verificado.
- Restauración probada con éxito en TEST.
- Plan de rollback documentado y comunicado.
