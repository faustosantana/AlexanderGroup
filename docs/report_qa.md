# Report QA — V2.3

Módulo `justech_alexander_reports` **19.0.3.1.0**.

## Separación

| Dimensión | Estado |
| --- | --- |
| PDF_RENDER | PASS (cotización, factura draft/posted, NC, recibos, estado, PO, facturas 5 empresas) |
| DESIGN | PENDING — checkpoint humano. No autoaprobado |
| FUNCTION | PASS — `document.company_id`, NCF del modelo, Pendiente en borrador, A5 recibo |
| FISCAL en PDF | PASS — NCF / NCF afectado leídos de `justech_do_ncf` |
| Delivery / picking PDF | NOT_TESTED |
| Multipágina 20/40/60 | NOT_TESTED esta corrida |

## Recibo

Paperformat `Doralex A5 Recibo` (875×1240 px @ 150 dpi vs A4 1240×1755).  
Anticipo: bloque **PAGO NO APLICADO / ANTICIPO** (no finge factura).  
Aplicado: tabla de facturas cuando hay `account.partial.reconcile`.

## Estado de cuenta

Corte: `account.move.line.date <= cutoff`, solo posted, cuenta receivable.  
Residual histórico: descuenta parciales con `max_date <= cutoff`.  
Invariantes (ejecutadas al renderizar):

- `abs(total - (vencido + no vencido)) < 0.01`
- `abs(total - suma aging) < 0.01`

Días: `Vencido N` / `Por vencer N` / `0`. Sin negativos.

PNG: [`docs/report_previews/v23/`](report_previews/v23/).

## Titular banco

`res.partner.bank.acc_holder_name` sigue siendo nombre personal (dato maestro).  
El PDF muestra **razón social de la compañía**. Confirmación humana pendiente si la cuenta es corporativa.
