# Plan y estado de deploy a producción — Doralex

Fecha: 2026-08-29. Autorización humana explícita para deploy controlado.
**No se copió la base DEV. No se cargaron rangos NCF ni datos QA.**

## Scorecard

| Flag | Valor |
| --- | --- |
| PRODUCTION_DEPLOYED | YES |
| PROD_BACKUP | PASS (`production_20260829_104748`) |
| PROD_HEALTH | PASS |
| REPORT_SUITE_PRODUCTION | PASS |
| EMAIL_PRODUCTION | 6/6 |
| MULTICOMPANY_PRODUCTION | PASS |
| PERMISSIONS_PRODUCTION | PASS |
| FISCAL_ENGINE_PRODUCTION | INSTALLED |
| NCF_PRODUCTION_RANGES | PENDING |
| NCF_PRODUCTION_SEQUENCES | PENDING |
| FISCAL_POSTING_READY | NO |
| SYSTEM_OPERATIONAL | YES |
| PROD_VISUAL_AUDIT | PASS |
| PROD_REPORTS_REAL_PNG | PASS (180 dpi desde PDF reales) |
| PROD_CROSS_COMPANY | PASS |
| PROD_EMAIL_ATTACHMENT_MATCH | 6/6 |
| PROD_RFQ_TITLE | PASS |
| PROD_PO_TITLE | PASS |
| PROD_RECEIPT_LAYOUT | PASS |
| PROD_DELIVERY_LAYOUT | PASS |
| PROD_MULTIPAGE | PASS |
| FISCAL_POSTING_GUARD | PASS |

## Backup

- Ruta: `/opt/doralex/backups/production/production_20260829_104748/`
- `db.dump` sha256 `f63061e2c400489232ead624f9ec9075465958d55ca2c6362ccc207668d4819c`
- Incluye: PostgreSQL, filestore, compose, `.env`, `odoo.conf`
- Meta pre-deploy: `/opt/doralex/backups/production/predeploy_meta_20260829_144741/`
- StartedAt pre-deploy: `2026-08-27T20:12:21Z`
- StartedAt post-deploy: `2026-08-29T14:56:35Z`

Rollback (probado a nivel de comandos, **no ejecutado**):

```bash
CONFIRM=yes ALLOW_PROD=yes bash /opt/doralex/scripts/restore.sh production production_20260829_104748
# revertir custom-addons y compose Graph si hace falta
bash /opt/doralex/scripts/healthcheck.sh production
```

## Módulos desplegados (solo target)

| MODULE | PROD_VERSION | TARGET_VERSION | SCHEMA_CHANGE | CONFIG_CHANGE | RISK |
| --- | --- | --- | --- | --- | --- |
| justech_alexander_base | none | 19.0.1.0.3 | YES | YES | MED |
| justech_alexander_reports | none | 19.0.3.8.5 | YES | YES | MED |
| justech_alexander_microsoft_mail | none | 19.0.1.0.4 | YES | YES | MED |
| justech_alexander_admin | none | 19.0.1.0.1 | YES | YES | LOW |
| justech_alexander_website | none | 19.0.1.0.7 | YES | YES (oculto) | LOW |
| justech_l10n_do_ncf | none | 19.0.2.31.0 | YES | YES (sin rangos) | HIGH |
| justech_l10n_do_base | none | 19.0.1.27.1 | YES | YES | MED |
| justech_fiscal_admin | none | 19.0.1.10.0 | YES | YES | MED |
| l10n_do_accounting | none | 19.0.1.0.1 | YES | YES | MED |
| justech_warranty | none | 19.0.1.9.1 | YES | NO | LOW |
| justech_core | none | 19.0.1.0.0 | YES | NO | LOW |
| justech_modules | none | 19.0.1.8.7 | YES | NO | LOW |
| justech_global_audit_log | none | 19.0.4.1.4 | YES | NO | LOW |
| justech_accounting_recovery | none | 19.0.1.4.0 | YES | YES | MED |
| bi_convert_purchase_from_sales | none | 19.0.0.0 | YES | NO | LOW |
| justech_report_identity_guard | none | 19.0.1.0.0 | NO | YES | LOW |

**No instalados** (congelados / fuera de alcance):  
`justech_purchase_sale_margin_control`, `justech_sale_purchase_trace`,
`multi_invoice_manual_payment_prod`, `justech_l10n_do_payments_withholding`,
`justech_approval_flow`, `justech_vendor_bill_po_control`.

Instalación: `-i` por módulo. **Nunca `-u all`.**

## Configuración aplicada (sobre DB PROD vacía)

PROD era Odoo 19 vanilla (`My Company`). Se crearon las 6 empresas reales
(identidad pública ya validada en DEV): razón social, RNC, dirección, teléfono,
correo `administracion@`, logo, Banreservas. No se copió la DB DEV.

- Graph: mount `/opt/doralex/secrets/microsoft` + `DX_MS_GRAPH_DIR` (secretos del host, no tokens DEV)
- Websites vacíos: no publicados
- Términos legales de compañía: vacíos (no inventados)
- Tasa USD: 0 (no inventada)
- Rangos NCF: **0**
- Usuario operacional `inversionesdoralex@gmail.com`: ventas/compras/facturación/inventario + multiempresa. **No** es administrador de sistema. Contraseña en `/opt/doralex/secrets/prod_operational_password` (no en Git)

## Fiscal post-deploy

| COMPANY | B01 | B02 | B04 | OTHER_TYPES | SEQUENCE | EXPIRATION | STATUS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DOR | NOT_CONFIGURED | NOT_CONFIGURED | NOT_CONFIGURED | — | PENDING | PENDING | ENGINE_READY |
| PIN | NOT_CONFIGURED | NOT_CONFIGURED | NOT_CONFIGURED | — | PENDING | PENDING | ENGINE_READY |
| DOM | NOT_CONFIGURED | NOT_CONFIGURED | NOT_CONFIGURED | — | PENDING | PENDING | ENGINE_READY |
| MAY | NOT_CONFIGURED | NOT_CONFIGURED | NOT_CONFIGURED | — | PENDING | PENDING | ENGINE_READY |
| REM | NOT_CONFIGURED | NOT_CONFIGURED | NOT_CONFIGURED | — | PENDING | PENDING | ENGINE_READY |
| BLU | NOT_CONFIGURED | NOT_CONFIGURED | NOT_CONFIGURED | — | PENDING | PENDING | ENGINE_READY |

Posteo fiscal sin rango: bloqueado con  
«Debe configurar un rango NCF válido para esta compañía y tipo de comprobante antes de contabilizar.»

## Smoke

- LOGIN HTTPS `/web/login` = 200
- Cotización PDF 6/6 + cruce de compañía activa
- DOR 40 líneas = 2 páginas; totales y firma en la última
- RFQ / OC / recepción (título RECEPCIÓN) / entrega
- Factura borrador: FACTURA + BORRADOR + Pendiente de NCF
- Email Graph 6/6 a buzón controlado (`fausto@justech.do`)
- DNS MX/SPF/DKIM/DMARC 6/6 (sin cambios)
- NCF_GUARD = PASS · rangos = 0

## Cierre visual post-deploy (2026-08-29)

Sin redesplegar. Sin rangos NCF. Sin posteo fiscal. PNG reales a 180 dpi
desde los PDF de `doralex_prod` (no bytes `%PDF` / wkhtmltopdf).

| Check | Resultado |
| --- | --- |
| Cotización 6/6 (logo, RNC, email, teléfono, banco, diseño V5.3) | PASS |
| Factura borrador 6/6: FACTURA + BORRADOR + Pendiente de NCF | PASS · 0 posted |
| Cruce BLU→REM, DOR→PIN, MAY→DOM | identidad del documento, no de la compañía activa |
| Sent Items FROM `administracion@` + adjunto PDF misma empresa | 6/6 · sin Gmail |
| RFQ = SOLICITUD DE COTIZACIÓN · PO = ORDEN DE COMPRA | PASS |
| Recepción: título RECEPCIÓN, proveedor, OC (PIN), tabla, sin calle duplicada | PASS |
| Entrega: ENTREGA, cliente, productos, Entregado por / Recibido por | PASS |
| Multipágina DOR/SO/00001: p1/2 sin total/firma; p2 header compacto + total + firmas | PASS |
| Guardia NCF sobre borrador QA | bloqueo claro · documento sigue draft · rangos = 0 |

Recepción usa masthead de texto (sin logo gráfico) — mismo criterio que DEV;
no se cambia a `external_layout` porque rompe `//main`.

## Datos pendientes (PROD vivo)

| COMPANY | WEBSITE | TERMS | USD RATE | BANK CONFIRMATION | NCF RANGES | NCF SEQUENCES | EXPIRATION | STATUS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DOR | EMPTY | EMPTY | NOT_CONFIGURED (USD.rate=1.0, 0 filas) | LOADED `9604436830` · pendiente confirmar humano | 0 | PENDING | PENDING | OPERATIONAL · NOT_FISCAL |
| PIN | EMPTY | EMPTY | NOT_CONFIGURED | LOADED `9604097492` · pendiente confirmar humano | 0 | PENDING | PENDING | OPERATIONAL · NOT_FISCAL |
| DOM | EMPTY | EMPTY | NOT_CONFIGURED | LOADED `9605588726` · pendiente confirmar humano | 0 | PENDING | PENDING | OPERATIONAL · NOT_FISCAL |
| MAY | EMPTY | EMPTY | NOT_CONFIGURED | LOADED `9605543104` · pendiente confirmar humano | 0 | PENDING | PENDING | OPERATIONAL · NOT_FISCAL |
| REM | EMPTY | EMPTY | NOT_CONFIGURED | LOADED `9608739498` · pendiente confirmar humano | 0 | PENDING | PENDING | OPERATIONAL · NOT_FISCAL |
| BLU | EMPTY | EMPTY | NOT_CONFIGURED | LOADED `9608670542` · pendiente confirmar humano | 0 | PENDING | PENDING | OPERATIONAL · NOT_FISCAL |

Website y términos vacíos a propósito (no inventados). Bancos ya salen en el PDF.

## Checklist para empezar a facturar

Orden exacto. No adelantar.

1. Cargar rangos NCF reales por empresa
2. Configurar secuencias
3. Configurar vencimientos
4. Validar tipo fiscal por journal
5. Cargar tasa USD si aplica
6. Confirmar términos
7. Revisar banco
8. Hacer primera factura controlada
9. Validar NCF
10. Validar PDF
11. Validar email
12. Registrar primer pago
13. Validar recibo
14. Hacer primera NC controlada

## Pendiente humano

1. Cargar rangos NCF reales DGII (prefix, start, end, current, expiration, journal)
2. Activar secuencias fiscales reales
3. Tasa USD si van a facturar en USD
4. Términos legales definitivos por empresa
5. Confirmar visualmente las cuentas Banreservas
6. Primera factura / NC / pago reales (solo después de 1–4)
