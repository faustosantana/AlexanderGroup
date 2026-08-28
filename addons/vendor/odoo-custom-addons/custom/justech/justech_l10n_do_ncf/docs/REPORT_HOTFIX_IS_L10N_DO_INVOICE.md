# Corrección fiscal de factura — `is_l10n_do_invoice`

## Qué es

`is_l10n_do_invoice` es un booleano QWeb definido por
`l10n_do_accounting.l10n_do_report_invoice_document`.

Cuando es `True`, el reporte muestra el bloque `#do_informations`
(Cliente, RNC/Cédula, razón social, dirección, tipo/NCF latam).
Cuando es `False`, ese bloque no se renderiza.

## Dónde se define (upstream)

En `l10n_do_accounting` (vista key
`l10n_do_accounting.l10n_do_report_invoice_document`), expresión original:

```xml
<t t-set="is_l10n_do_invoice"
   t-value="o.l10n_latam_use_documents
            and o.company_id.country_id
            and o.company_id.l10n_do_country_code == 'DO'"/>
```

## Por qué quedaba `False`

Tras el Go-Live del Motor Fiscal Justech, los diarios/movimientos
 dominicanos pueden tener:

- `company.l10n_do_country_code == 'DO'`
- NCF / tipo Justech (`justech_do_ncf`, `justech_do_document_type_id`)
- a veces `l10n_latam_document_number`

pero `o.l10n_latam_use_documents` en `False`, porque el motor ya no depende
del flag latam del diario.

Eso es **esperado tras el cutover Justech**, no un fallo de Studio.
Consecuencia en QWeb: `is_l10n_do_invoice=False` → desaparecen cliente,
RNC/Cédula y bloque fiscal DO, aunque el NCF exista.

## Solución Justech (reproducible)

Plantilla
`justech_l10n_do_ncf.report_invoice_document_justech_l10n_do_gate`
reemplaza únicamente el `t-set` con:

```python
bool(o.company_id.country_id and o.company_id.l10n_do_country_code == 'DO')
```

Criterio: la compañía es dominicana (`l10n_do_country_code == 'DO'`).
Así vuelven Cliente/RNC también en borradores sin NCF todavía asignado,
tras el cutover donde `l10n_latam_use_documents` queda en `False`.

## Qué no hace

- No pone `True` fijo (exige compañía DO real).
- No activa `l10n_latam_use_documents` en diarios/compañías.
- No modifica NCF, tipos, contactos ni asientos.
- No muestra bloque DO en empresas con `l10n_do_country_code != 'DO'`
  (otras localizaciones / extranjeras).

## Studio (cotizaciones)

Vista key
`web_studio.report_editor_customization_diff.view._web.address_layout`
(`inherit_id` → `web.address_layout`) reemplaza `address` e
`information_block` por `<br/>`. Se desactiva en
`migrations/19.0.2.6.0/post-migrate.py` por key + fingerprint.
