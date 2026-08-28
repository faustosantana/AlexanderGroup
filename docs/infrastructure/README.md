# docs/infrastructure/ — Índice

Documentación de infraestructura del servidor nuevo de Doralex / Alexander Group
(Odoo 19, Produccion + Dev aislados).

| Documento | Contenido |
| --------- | --------- |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Arquitectura aislada (Docker, redes, volúmenes, puertos, proxy, SSL). |
| [`SERVER_AUDIT.md`](SERVER_AUDIT.md) | Auditoría del servidor (**PENDING** hasta SSH). |
| [`DEPLOYMENT_RUNBOOK.md`](DEPLOYMENT_RUNBOOK.md) | Flujo LOCAL→GIT→DEV→TESTS→VALIDACION→BACKUP→DEPLOY. |
| [`ISOLATION_VALIDATION.md`](ISOLATION_VALIDATION.md) | Checklist de aislamiento (PASS/FAIL). |
| [`DNS_AND_SSL.md`](DNS_AND_SSL.md) | Dominios definitivos `.cloud`, `DNS_REQUIRED`, certificados. |
| [`MAIL_DNS_CLOSEOUT.md`](MAIL_DNS_CLOSEOUT.md) | MX/SPF/DKIM/DMARC de los 6 dominios de correo. |
| [`MAIL_FUNCTIONAL_TEST.md`](MAIL_FUNCTIONAL_TEST.md) | Prueba funcional DEV: cotización, factura, aliases, aislamiento. |
| [`MAIL_PRIMARY_FROM.md`](MAIL_PRIMARY_FROM.md) | From único `administracion@` por `document.company_id`. |
| [`SECURITY_HARDENING.md`](SECURITY_HARDENING.md) | Endurecimiento de SSH, firewall, secretos. |
| [`BACKUP_STRATEGY.md`](BACKUP_STRATEGY.md) | Estrategia de backups verificables. |
| [`ENTERPRISE_READINESS.md`](ENTERPRISE_READINESS.md) | Odoo 19 Enterprise (`ENTERPRISE_SOURCE_PENDING`). |
| [`STUDIO_AND_REPORTS.md`](STUDIO_AND_REPORTS.md) | Preparación de Odoo Studio y reportes PDF (QWeb). |
| [`../migration/JUSTGROUP_TECHNICAL_REFERENCE.md`](../migration/JUSTGROUP_TECHNICAL_REFERENCE.md) | Referencia técnica de Justgroup (paridad de versión). |

Servidor objetivo: `2.25.121.111` (user `root`). Dominios definitivos:
`doralexgroup.cloud` (Prod), `dev.doralexgroup.cloud` (Dev),
`www.doralexgroup.cloud` (→ canónico). Acceso por **llave SSH** (ver `SERVER_AUDIT.md`).
