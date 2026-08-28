# Cierre DNS de correo — 6 dominios Doralex

Fecha: 2026-08-28. Tenant `doralex.onmicrosoft.com`.
**PROD Odoo / Doralex PROD no se tocaron.**

## Resultado

```text
MX = 6/6
SPF = 6/6
AUTODISCOVER = 6/6
DKIM = 6/6
DMARC = 6/6
EXCHANGE_DKIM_ENABLED = 6/6
MAIL_FLOW_TEST = 6/6
ODOO_OUTGOING_MAIL = PASS
ODOO_INCOMING_MAIL = PASS
MULTICOMPANY_MAIL_ISOLATION = PASS
READY_FOR_MAIL_PRODUCTION = YES
DORALEX MULTI-COMPANY M365 MAIL = COMPLETED
```

DKIM Exchange `Enabled=True Status=Valid` en los 6 dominios.
Piñaria/Rempart: `_dmarc p=none` (no subir a quarantine/reject todavía).
GoDaddy: DMARC `p=quarantine` conservado. DNS GoDaddy no se modificó en este cierre.

Plan DMARC posterior: rua 7–14 días → quarantine (Piñaria/Rempart) → reject cuando haya alineación.
