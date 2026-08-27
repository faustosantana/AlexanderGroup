# Hotfix moneda + vigencia NCF (19.0.2.7.0)

## Impuestos DOP

| Dato | Valor |
|------|--------|
| Template | `account.document_tax_totals_company_currency_template` |
| XML ID | `account.document_tax_totals_company_currency_template` |
| Llamado desde | `account.report_invoice_document` |
| Condición | `o.tax_totals.get('display_in_company_currency')` |
| Activación | `company.display_invoice_tax_company_currency` y moneda doc ≠ compañía |
| Render | `Impuestos <span t-field="o.company_currency_id"/>` → **Impuestos DOP** |

Justech oculta el `div.totals_taxes_company_currency` vía herencia QWeb.
No altera montos ni monedas del documento.

## Válida hasta

| Dato | Valor |
|------|--------|
| Etiqueta | `#fiscal_exp_date` en `l10n_do_accounting.l10n_do_report_invoice_document` |
| Campo leído (legacy) | `account.move.l10n_do_ncf_expiration_date` |
| Fuente Justech | `justech_do_ncf_range_id.date_to` |
| Caso FC/2026/00376 | NCF B0100001617 → rango B01 `date_to=2026-12-31`; expiration_date vacío |

Causa: **B** (campo incorrecto / no migrado al campo legacy) + etiqueta visible sin valor.

Regla QWeb: mostrar fecha (`legacy` o `range.date_to`); si no hay fecha, ocultar etiqueta.
