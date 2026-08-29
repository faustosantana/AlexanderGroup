# Multiempresa QA

`document.company_id` controló journal, tax, NCF, banco en PDF, From de correo.

## Cruces (sesión activa ≠ documento)

| Activo | Documento | Resultado |
| --- | --- | --- |
| DOR | cotización PIN | identidad PIN |
| BLU | cotización REM | identidad REM |
| MAY | cotización DOM | identidad DOM |

NCF B01/B04 de cada empresa en su propia banda `9910x`. Sin leakage de RNC/email/banco.

`justech_report_identity_guard`: plantilla `justech_report_design.report_hellenia_invoice` bloqueada.
