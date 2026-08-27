# docs/infrastructure/ — Índice

Documentación de infraestructura del servidor nuevo de Doralex / Alexander Group
(Odoo 19, Produccion + Dev aislados).

| Documento | Contenido |
| --------- | --------- |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Arquitectura aislada (Docker, redes, volúmenes, puertos, proxy, SSL). |
| [`SERVER_AUDIT.md`](SERVER_AUDIT.md) | Auditoría del servidor (**PENDING** hasta SSH). |
| [`DEPLOYMENT_RUNBOOK.md`](DEPLOYMENT_RUNBOOK.md) | Flujo LOCAL→GIT→DEV→TESTS→VALIDACION→BACKUP→DEPLOY. |
| [`ISOLATION_VALIDATION.md`](ISOLATION_VALIDATION.md) | Checklist de aislamiento (PASS/FAIL). |
| [`DNS_AND_SSL.md`](DNS_AND_SSL.md) | Dominios previstos, `PENDING_DNS`, emisión de certificados. |
| [`SECURITY_HARDENING.md`](SECURITY_HARDENING.md) | Endurecimiento de SSH, firewall, secretos. |
| [`BACKUP_STRATEGY.md`](BACKUP_STRATEGY.md) | Estrategia de backups verificables. |
| [`ENTERPRISE_READINESS.md`](ENTERPRISE_READINESS.md) | Estado de Odoo 19 Enterprise (licencia/fuente). |

Servidor objetivo: `2.25.121.111` (user `root`). **No** se accede por SSH hasta
que se autorice y se entregue la contraseña (ver `SERVER_AUDIT.md`).
