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

## 7. Límite STAGING

Publicar factura de proveedor exige tipo 606 + NCF proveedor + comprobante
**B11/B13/B17 emitido por la empresa**. En Doralex (id 11) solo hay rangos
activos B01 y B15. **No se creó rango B11.** Por eso el pago real con
asiento de retención quedó BLOCKED; el cálculo del catálogo sí se validó.
