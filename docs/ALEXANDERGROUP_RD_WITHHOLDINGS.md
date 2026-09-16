# Catálogo de retenciones República Dominicana — Alexander / Doralex

Fecha de implementación: **2026-09-16**.
Entorno: **solo STAGING**. **PROD TOUCHED: NO.**

Fuentes normativas consultadas al momento del desarrollo:

- Ley 30-26 (promulgada 18/06/2026); retenciones Art. 309 vigentes **desde 01/07/2026** (Aviso DGII 10-26 / calendario oficial).
- Comunidad DGII CA59 (servicios técnicos PF: 15% sobre renta presunta 20%).
- Art. 305, 305-1, 305-2, 306, 306 bis, 308, 309 del Código Tributario.
- Reglamento 139-98 Art. 70; Normas 02-05, 01-11, 07-09, 08-10, R293-11.

No se automatiza la retención por tipo de contacto. El usuario **selecciona**
la regla en el wizard de pago; el sistema calcula BASE / % / MONTO.

## 1. CONFIG ACTUAL vs NORMA VIGENTE

Los impuestos `account.tax` de compra **no se modificaron**.

| CONFIG ACTUAL (impuesto l10n_do) | NORMA VIGENTE (01/07/2026) | CAMBIO PROPUESTO |
| --- | --- | --- |
| `-10% ISR Fee` | 15% ISR honorarios PF (Art. 309 b) | Usar `DX-ISR-PROF-PF-15`. No cambiar el -10%. |
| `-10% ISR Rent.` | 15% ISR alquiler PF (Art. 309 a) | Usar `DX-ISR-ALQ-PF-15`. No cambiar el -10%. |
| `-2% ISR (N07-07)` | 15% × 20% presunta = 3% efectivo | Usar `DX-ISR-TEC-PF-15`. No cambiar el -2%. |
| `-27% ISR (L253-12)` para todo el exterior | 15% regalías/software/ads/datos; 27% residual Art. 305 | Usar `DX-ISR-EXT-*`. No cambiar el -27%. |
| `-5% ISR Gov.` (`type_tax_use=sale`) | 5% cuando el **Estado** paga (Art. 309 e) | Usar `DX-ISR-ESTADO-5` solo si Alexander es pagador estatal. |
| `-30% ITBIS` como -5.4 del subtotal | 30% **del ITBIS facturado** (N02-05) | Catálogo `DX-ITBIS-30-PJ` con `base_type=itbis`. |
| `-100% ITBIS` | 100% del ITBIS facturado | Catálogo `DX-ITBIS-100-PF`. |

## 2. Catálogo Alexander (`DX-*`)

Códigos globales (`company_id` vacío). Cuenta por empresa en
`justech.do.withholding.company.config`.

| Código | Nombre | Tipo | Tasa | Base | Vigencia | Fuente | Cuenta (nombre l10n_do) | 606/623 | Aplicabilidad | Exclusiones |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DX-ISR-ESTADO-5 | Proveedor del Estado 5% | ISR | 5 | untaxed | 2026-07-01 | Art. 309 e | Other Withholdings (N07-07) | 606/623 | Pagador estatal | No automático si prevalece ISR PF |
| DX-ISR-PROF-PF-15 | Profesionales PF 15% | ISR | 15 | untaxed | 2026-07-01 | Art. 309 b | Other Withholdings (N07-07) | 606/623 | Honorarios/comisiones/asesorías PF | No entre PJ-PJ |
| DX-ISR-TEC-PF-15 | Técnicos PF 15%×20% | ISR | 15 | untaxed + presunta 20% | 2026-07-01 | Art. 309 + Regl. 139-98 Art. 70 | Other Withholdings (N07-07) | 606/623 | Oficios técnicos PF | No honorarios profesionales |
| DX-ISR-ALQ-PF-15 | Alquiler PF 15% | ISR | 15 | untaxed | 2026-07-01 | Art. 309 a (único y definitivo) | ISR withheld on rent paid to individuals | 606/623 | Alquiler mueble/inmueble a PF | ITBIS aparte |
| DX-ITBIS-30-PJ | ITBIS 30% PJ | ITBIS | 30 | **ITBIS facturado** | N02-05 | Norma 02-05 | ITBIS Withheld from Legal Entity (N02-05) | 606 | Servicios liberales / alquiler muebles PJ-PJ | No toda factura; revisar e-CF |
| DX-ITBIS-100-PF | ITBIS 100% PF | ITBIS | 100 | ITBIS facturado | R293-11 | R293-11 / IT-1 | ITBIS Withheld from Individuals (R293-11) | 606 | PF servicio gravado a PJ | ISR independiente |
| DX-ITBIS-100-SEG | ITBIS 100% seguridad | ITBIS | 100 | itbis | — | Supuesto especial | ITBIS Withheld for Professional Services (N02-05) | 606 | Seguridad/vigilancia | Manual |
| DX-ITBIS-100-ESFL | ITBIS 100% ESFL | ITBIS | 100 | itbis | N01-11 | N01-11 | ITBIS Withheld from Non-Profit Entities (N01-11) | 606 | ESFL | Manual |
| DX-ITBIS-100-INF | Informal / RST | ITBIS | 100 | itbis | N08-10 | N08-10 / RST | ITBIS Withheld from Informal Goods (N08-10) | 606 | Informal/RST si la norma del caso lo exige | No automático |
| DX-ISR-DIV-10 | Dividendos 10% | ISR | 10 | untaxed | vigente | Art. 308 | Other Withholdings | 623 / IR-17 | Dividendos | No operativo de proveedores |
| DX-ISR-INT-PF-10 | Intereses PF 10% | ISR | 10 | untaxed | vigente | Art. 306 bis | ISR withheld on interest paid | 623 | Intereses a PF residente | — |
| DX-ISR-INT-EXT-10 | Intereses exterior 10% | ISR | 10 | untaxed | vigente | Art. 306 | ISR Withheld on Interest Paid Abroad | 623 | Intereses a no residente | Revisar CDI |
| DX-ISR-EXT-REG-15 | Exterior regalías 15% | ISR | 15 | untaxed | 2026-07-01 | Art. 305-1 | ISR Withheld on Remittances Abroad (L253-12) | 623 | Regalías | No 27% automático |
| DX-ISR-EXT-SW-15 | Exterior software 15% | ISR | 15 | untaxed | 2026-07-01 | Art. 305-2 | idem | 623 | Licencia (no cesión de propiedad) | — |
| DX-ISR-EXT-ADS-15 | Exterior ads 15% | ISR | 15 | untaxed | 2026-07-01 | Art. 305-2 | idem | 623 | Publicidad en línea | — |
| DX-ISR-EXT-DATA-15 | Exterior datos/nube 15% | ISR | 15 | untaxed | 2026-07-01 | Art. 305-2 | idem | 623 | Hosting / datos | — |
| DX-ISR-EXT-27 | Exterior residual 27% | ISR | 27 | untaxed | vigente | Art. 305 | idem | 623 | Fuente dominicana sin tasa especial | Último recurso |
| DX-ISR-PREMIO-25 | Premios 25% | ISR | 25 | untaxed | 2026-07-01 | Art. 309 c | Other Withholdings | 623 | Loterías/sorteos | Bancas tienen escala |
| DX-ISR-OTRAS-15 | Otras Art. 309 f | ISR | 15 | untaxed | 2026-07-01 | Art. 309 f | Other Withholdings (N07-07) | 623 | Rentas no enumeradas | No comodín |

## 3. Fórmulas

```
ISR profesional / alquiler / Estado / dividendos / intereses / exterior:
  retención = base_untaxed × tasa / 100

ISR técnico PF:
  base_original = subtotal (sin ITBIS)
  base_presunta = base_original × 20%
  retención    = base_presunta × 15%
               = 3% del bruto sujeto

ITBIS 30% / 100%:
  retención = ITBIS_facturado × tasa / 100
  NUNCA = subtotal × 30%
```

Pago parcial: se prorratea contra `amount_total` de la factura
(comportamiento del módulo `justech_l10n_do_payments_withholding`).

## 4. Ejemplos (STAGING, 2026-09-16)

| Escenario | Base | ITBIS | ISR | RET ITBIS | Total | Neto | Resultado |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PJ→PJ sin retención | 100000 | 18000 | 0 | 0 | 118000 | 118000 | selección vacía |
| PJ→PJ ITBIS 30% | 100000 | 18000 | 0 | 5400 | 118000 | 112600 | `DX-ITBIS-30-PJ` = 5400 |
| PF profesional | 100000 | 18000 | 15000 | 0 | 118000 | 103000 | `DX-ISR-PROF-PF-15` |
| PF técnico | 100000 | 18000 | 3000 | 0 | 118000 | 115000 | `DX-ISR-TEC-PF-15` |
| PF + 100% ITBIS + ISR 15% | 100000 | 18000 | 15000 | 18000 | 118000 | 85000 | multi-retención |
| Estado 5% | 100000 | 18000 | 5000 | 0 | 118000 | 113000 | `DX-ISR-ESTADO-5` |
| Parcial 50% de 118000 + ITBIS 30% | 50000 eq. | 9000 | 0 | 2700 | — | — | prorrateo |

Empresas 8 (Blue Elite) y 11 (Doralex) resuelven las mismas **cuentas por nombre**,
no por `account_id` compartido a ciegas.

## 5. Cuentas (COMPANY / CONCEPTO / EXISTE)

No se crearon cuentas nuevas. Lookup por nombre + `company_ids`.

| COMPANY | CONCEPTO | ACCOUNT NAME | TIPO | EXISTE/CREAR |
| --- | --- | --- | --- | --- |
| 8–13 | ISR operativo / Estado / técnico / profesional | Other Withholdings (N07-07) | liability_non_current | EXISTE |
| 8–13 | ISR alquiler PF | ISR withheld on rent paid to individuals | liability_non_current | EXISTE |
| 8–13 | ISR intereses | ISR withheld on interest paid | liability_non_current | EXISTE |
| 8–13 | ISR exterior | ISR Withheld on Remittances Abroad (L253-12) | liability_non_current | EXISTE |
| 8–13 | ITBIS 30% PJ | ITBIS Withheld from Legal Entity (N02-05) | liability_non_current | EXISTE |
| 8–13 | ITBIS 100% PF | ITBIS Withheld from Individuals (R293-11) | liability_non_current | EXISTE |
| 8–13 | ITBIS ESFL | ITBIS Withheld from Non-Profit Entities (N01-11) | liability_non_current | EXISTE |

## 6. UX

Wizard `justech.payment.partner.wizard`: el usuario marca facturas y
**elige** `withholding_catalog_ids`. `apply` default False. Muestra
base, tasa y monto. No se retiene por ser PF/PJ.

## 7. Circuito contable STAGING (2026-09-16)

Empresa UAT: **INVERSIONES DORALEX,S.RL.** (id 11). **PROD no tocado.**

Arquitectura Justech: compras **recibidas** (NCF del proveedor, LATAM B01)
no consumen rango de la empresa. Compras **emitidas** (informal PF) consumen
**B11** de la empresa. B13 (gastos menores) y B17 (exterior) **no** se
crearon: no aplican a estos casos.

| Escenario | Tipo NCF | Documento | Pago | Retención | Residual |
| --- | --- | --- | --- | --- | --- |
| PF profesional + ITBIS 100 | B11 emitido `B1199111001` | `BILL/2026/09/0001` 118 000 | `PBNK1/2026/00082` banco 85 000 | ISR 15 000 + ITBIS 18 000 | 0 |
| PF técnico 15%×20% | B11 emitido `B1199111002` | `BILL/2026/09/0002` 118 000 | `PBNK1/2026/00083` banco 115 000 | ISR 3 000 | 0 |
| Estado 5% | B01 recibido `B0188000011` | `BILL/2026/09/0003` 118 000 | banco 113 000 | ISR 5 000 | 0 |
| ITBIS 30% PJ | B01 recibido `B0188000012` | `BILL/2026/09/0004` 118 000 | banco 112 600 | ITBIS 5 400 (nunca 30 000) | 0 |
| Multi A/B/C + WH | B11 `B1199111003–005` | 118 000 / 59 000 / 29 500 | `PBNK1/2026/00086` 148 750 | 57 750 | 0/0/0 |
| Parcial ITBIS 30 | B01 recibido | `BILL/2026/09/0008` | 56 300 + 56 300 | 2 700 + 2 700 | 0 |

### Técnico — desglose visible

Catálogo `DX-ISR-TEC-PF-15` (`dx_presumed_income_pct=20`, `rate=15`):

| Campo | Valor |
| --- | --- |
| BASE ORIGINAL | 100 000 |
| BASE SUJETA/PRESUNTA | 20 000 (20% del bruto) |
| TASA | 15% |
| RETENCIÓN | 3 000 |
| `base_label` | Base presunta (20% del bruto) |

El usuario no ve solo «3%»: ve base presunta 20 000 × 15%.

### Asientos de pago (COMPANY / RULE / ACCOUNT / DEBIT / CREDIT / BALANCE)

INVERSIONES DORALEX — `PBNK1/2026/00082` (PF + ITBIS 100):

| RULE | ACCOUNT CODE | ACCOUNT NAME | DEBIT | CREDIT | BALANCE |
| --- | --- | --- | --- | --- | --- |
| Banco / outstanding BNK1 | 11010204 | Outstanding Payments | 0 | 85 000 | −85 000 |
| CxP proveedor | 21010200 | Accounts Payable to Local Suppliers | 118 000 | 0 | 118 000 |
| ISR profesional | 21030308 | Other Withholdings (N07-07) | 0 | 15 000 | −15 000 |
| ITBIS 100 PF | 21030202 | ITBIS Withheld from Individuals (R293-11) | 0 | 18 000 | −18 000 |

ITBIS 30 PJ — cuenta **21030201** ITBIS Withheld from Legal Entity (N02-05),
haber 5 400. Técnico/Estado — misma 21030308, haber 3 000 / 5 000.
Factura de compra: 51010100 Cost of Goods 100 000 / 11080101 ITBIS Paid on
Purchases 18 000 / 21010200 CxP 118 000.

Odoo 19 deja el banco en **Outstanding Payments** del diario BNK1
(`payment_state=in_process`) hasta extracto. No es write-off ni asiento
manual. Conciliación: `account.partial.reconcile` sobre CxP; residual 0.

### Pago parcial — cómo Odoo prorratea

Fórmula del módulo: retención × (`amount_to_pay` / `amount_total`).
Factura 118 000, ITBIS 30% = 5 400.

| Pago | Aplicado | Retención reconocida | Banco | Residual |
| --- | --- | --- | --- | --- |
| 1 | 59 000 | 2 700 | 56 300 | 59 000 |
| 2 | 59 000 | 2 700 | 56 300 | 0 |
| Total | 118 000 | 5 400 | 112 600 | 0 |

El wizard puede mostrar base ITBIS 18 000 en ambos tramos; el **monto**
retenido sí es la mitad. No se modificó el motor.

### Recibo

`justech_alexander_reports` **19.0.3.9.1** (bug UAT: el compose solo leía
CxC y marcaba pagos a proveedor como no aplicados). Ahora el PDF muestra
factura, bruto, ISR, ITBIS, otras, neto y total aplicado.
Evidencia: `PBNK1/2026/00082` HTML/PDF; multi `PBNK1/2026/00086` 3 facturas.

### Impuestos legacy (−10% / −2% / −27%)

Siguen activos. **No se modificaron.** En facturas UAT nuevas solo se
asignó `18% ITBIS`. No son default. No interfieren con DX-*.

Recomendación futura (NO ejecutar):

| Impuesto | Recomendación |
| --- | --- |
| −10% ISR Fee / Rent. | ARCHIVE (histórico) → MIGRATE a DX-ISR-PROF / ALQ |
| −2% ISR (N07-07) | ARCHIVE → MIGRATE a DX-ISR-TEC-PF-15 |
| −27% ISR (L253-12) | KEEP para residual Art. 305; no default |
| −30% ITBIS (−5.4) | ARCHIVE → usar DX-ITBIS-30-PJ (base ITBIS) |

## 8. Rangos NCF STAGING/UAT (solo empresa 11)

Históricos **no** reactivados. B01 Excel 52–87 y B15 141–160 intactos.

| COMPANY | TIPO | USO | RANGO ACTUAL | ESTADO | UAT | INICIAL | FINAL | RIESGO |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DOR 11 | B04 | NC ventas H01 | RNG 14 99110001–050 | cancelled | RNG 34 99114001–050 auth STAGING-UAT-NO-DGII-20260916 | 99114001 | 99114050 | Bajo |
| DOR 11 | B11 | Compras informal PF | ninguno | no existía | RNG 35 99111001–150 misma auth | 99111001 | 99111150 | Medio (use_ncf en BILL) |
| DOR 11 | B13 | Gastos menores | — | no crear | — | — | — | No aplica |
| DOR 11 | B17 | Exterior | — | no crear | — | — | — | Catálogo solo |
| DOR 11 | B01 recibido | PJ / Estado | N/A | N/A | NCF proveedor UAT `B01880000xx` | — | — | No consume rango empresa |

**NO copiar estos rangos a PROD.** PROD debe auditar secuencias reales
DGII por empresa antes del GO.
