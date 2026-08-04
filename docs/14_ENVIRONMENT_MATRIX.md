# 14 — Matriz de Ambientes

> Valores **pendientes** hasta definir infraestructura (Fase 3). No se asumen
> servidores, IPs ni dominios.

## Ambientes

| Aspecto              | DEV       | TEST      | PROD      |
| -------------------- | --------- | --------- | --------- |
| Propósito            | Desarrollo | Pruebas/UAT | Producción |
| Servidor / host      | Pendiente | Pendiente | Pendiente |
| Dominio              | Pendiente | Pendiente | Pendiente |
| Versión Odoo         | 19 (por fijar) | 19 (por fijar) | 19 (por fijar) |
| Community/Enterprise | Pendiente | Pendiente | Pendiente |
| PostgreSQL           | Pendiente | Pendiente | Pendiente |
| Datos                | Ficticios | Anonimizados/UAT | Reales |
| Backups              | Opcional  | Sí        | Sí (crítico) |
| Acceso               | Equipo dev | Equipo + usuarios UAT | Restringido |
| Despliegue           | Manual    | Controlado | Controlado + rollback |
| Monitoreo            | Básico    | Básico    | Completo  |

## Reglas

- Los secretos por ambiente se gestionan fuera de Git (`.env` no versionado).
- PROD nunca usa contraseñas por defecto ni datos demo con información personal.
- Cambios llegan a PROD solo por el flujo de ramas ([`07_BRANCHING_STRATEGY.md`](07_BRANCHING_STRATEGY.md)).
