# 06 — Saldo bajo (diagnóstico, sin email)

Umbral: WARNING ≤10 · CRITICAL ≤3 · EXHAUSTED = 0 · EXPIRED si `date_to < today`.
No autorenueva. No inventa rangos. No dispara cron de mail.

| Empresa | Remaining | Nivel | Flag |
| --- | --- | --- | --- |
| Doralex B15 | 9 | WARNING | DORALEX_B15_LOW_BALANCE = YES |
| El Mayuma B15 | 6 | WARNING | MAYUMA_B15_LOW_BALANCE = YES |
| Rempart B15 | 2 | CRITICAL | REMPART_B15_LOW_BALANCE = YES |

Pendiente operativo Rempart: solicitar / confirmar nuevo rango B15 **antes**
de agotar 112 y 113. Los dos números válidos permanecen activos.

Vista: lista nativa `justech.do.ncf.range` (Centro de Rangos existente) +
columnas overlay `Último`, `Alerta`, `Autorización`. No se creó una app nueva.

`dx_preview_next_ncf()` lee `next_ncf_display` y no consume.
