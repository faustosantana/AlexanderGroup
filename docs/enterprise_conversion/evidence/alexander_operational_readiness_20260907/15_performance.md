# 15 — Performance (medido, sin tuning)

| ITEM | CURRENT | RECOMMENDED | ACTION | RISK |
|---|---|---|---|---|
| Host RAM | 7.8 Gi total / ~3.6 Gi available | observar; 3 stacks en el mismo host | no tunear | MEDIUM |
| Swap | 0 | opcional 2–4G si hay presión | no tunear ahora | MEDIUM |
| Disk | 96G / 13G used (13%) | >20% free | none | LOW |
| Prod Odoo RSS | ~1.96 Gi / 7.76 Gi | workers 4 + cron 2 encajan | none | LOW |
| Prod Odoo CPU snapshot | 100% puntual durante shell | idle esperado ~bajo | none; spike de probe | LOW |
| Staging Odoo | 487 Mi / 0% CPU | OK | none | LOW |
| Prod DB | 219 Mi | OK (~190–220 Mi) | none | LOW |
| workers | 4 | 4 razonable para 8G / 6 compañías | none | LOW |
| max_cron_threads | 2 | 1–2 | none | LOW |
| limit_memory_soft/hard | 2.0 / 2.5 Gi | no subir a ciegas | none | LOW |
| limit_time_cpu/real | 600 / 1200 | OK reportes | none | LOW |
| Filestore | creció con 26 PDFs (~23 Mi backup) | OK | none | LOW |
| Mail queue | 0 sent/outgoing | n/a | none | LOW |
| Website / nginx / SSL | no tocado | no cambiar | none | LOW |

Enterprise: `web_enterprise` 19.0.1.0 installed; expiration `2026-10-06 14:54:41`; db UUID `4368f2f6-a253-11f1-9f8c-a7d8786898ca`. No es licencia Justgroup.

Crons activos: 64. Ninguno e-CF/DGII send. Incluye mail digest, account followup, website snippet (website no se rediseñó).
