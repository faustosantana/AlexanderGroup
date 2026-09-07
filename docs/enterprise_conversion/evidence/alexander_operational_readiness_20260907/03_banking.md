# 03 — Bancos y saldos de apertura

Fecha Excel original: `05//08/2026` (inválida). **No se posteó ningún asiento.**

| COMPANY | EXCEL_OPENING_BANK_BALANCE | ODOO_POSTED_BALANCE | OPENING_ENTRY_EXISTS | ACTION |
|---|---|---|---|---|
| INVERSIONES DORALEX,S.RL. | 5,000,000.00 | 0.00 | NO | WAIT_VALID_DATE |
| COMERCIALIZADORA DE ALIMENTOS PIÑARIA, S.R.L. | 2,450,000.00 | 0.00 | NO | WAIT_VALID_DATE |
| DOMINION BUSINESS,S.R.L. | 1,500,000.00 | 0.00 | NO | WAIT_VALID_DATE |
| INVERSIONES EL MAYUMA, S.R.L. | 3,000,000.00 | 0.00 | NO | WAIT_VALID_DATE |
| REMPART GROUP S.R.L. | 4,600,000.00 | 0.00 | NO | WAIT_VALID_DATE |
| BLUE ELITE, S.R.L. | 1,250,000.00 | 0.00 | NO | WAIT_VALID_DATE |

Suma Excel no posteada: 18,800,000.00 DOP.

## Cuentas Banreservas (números no cambiados)

| COMPANY | JOURNAL | ACC_NUMBER | CURRENCY | COMPANY | GL | INBOUND | OUTBOUND | STATUS |
|---|---|---|---|---|---|---|---|---|
| BLUE ELITE | Banco Banreservas · BLU | 9608670542 | DOP | 8 | 11010201 | yes | yes | NUMBER_DEFINITIVE / BALANCE_PENDING |
| PIÑARIA | Banco Banreservas · PIN | 9604097492 | DOP | 9 | 11010201 | yes | yes | NUMBER_DEFINITIVE / BALANCE_PENDING |
| DOMINION | Banco Banreservas · DOM | 9605588726 | DOP | 10 | 11010201 | yes | yes | NUMBER_DEFINITIVE / BALANCE_PENDING |
| DORALEX | Banco Banreservas · DOR | 9604436830 | DOP | 11 | 11010201 | yes | yes | NUMBER_DEFINITIVE / BALANCE_PENDING |
| EL MAYUMA | Banco Banreservas · MAY | 9605543104 | DOP | 12 | 11010201 | yes | yes | NUMBER_DEFINITIVE / BALANCE_PENDING |
| REMPART | Banco Banreservas · REM | 9608739498 | DOP | 13 | 11010201 | yes | yes | NUMBER_DEFINITIVE / BALANCE_PENDING |

Fix determinístico 2026-09-07: se ligó `res.partner.bank` existente al diario (`op_ready_bank_link.json`). No se creó otra cuenta Banreservas.

Outstanding receipts/payments en líneas de método: vacíos (Odoo usa default del diario si no hay override). No se inventaron cuentas outstanding.

Caja: 0 diarios `cash` en las 6. Excel no entregó caja. `NOT_APPLICABLE` hasta confirmación.

QA_CONFIGURATION residual: rangos NCF 9910 cancelados; pagos `PBNK1/2026/0000x` de pruebas siguen posteados (ver 04 / 11). No se borraron.
