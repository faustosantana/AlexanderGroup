# Fiscal QA — NCF TEST y 606/607/608

## Rangos TEST (no DGII)

`authorization_number = DX-TEST-NO-DGII-360`  
Nombre: `DX TEST Bxx CCC — … — NO FISCAL REAL — NO ENVIAR DGII`  
Banda `991xxxxx` (distinta de DEV `990xxxxx`).

| COMPANY | TYPE | TEST_RANGE | FIRST | LAST | USED | DOCUMENTS |
| --- | --- | --- | --- | --- | --- | --- |
| DOR | B01 | id 13 | 99100001 | 99100050 | 2 | B0199100001 factura; B0199100002 vencida |
| DOR | B04 | id 14 | 99110001 | 99110050 | 1 | B0499110001 NC de B0199100001 |
| PIN | B01 | id 15 | 99100101 | 99100150 | 4 | B0199100101 factura; 0102/0104 void 608; 0103 vencida |
| PIN | B04 | id 16 | 99110101 | 99110150 | 1 | B0499110101 |
| DOM | B01 | id 17 | 99100201 | 99100250 | 2 | B0199100201 / 0202 |
| DOM | B04 | id 18 | 99110201 | 99110250 | 1 | B0499110201 |
| MAY | B01 | id 19 | 99100301 | 99100350 | 2 | B0199100301 / 0302 |
| MAY | B04 | id 20 | 99110301 | 99110350 | 1 | B0499110301 |
| REM | B01 | id 21 | 99100401 | 99100450 | 2 | B0199100401 / 0402 |
| REM | B04 | id 22 | 99110401 | 99110450 | 1 | B0499110401 |
| BLU | B01 | id 23 | 99100501 | 99100550 | 2 | B0199100501 / 0502 |
| BLU | B04 | id 24 | 99110501 | 99110550 | 1 | B0499110501 |

Vendor NCF recibidos (LATAM, no consumen rango empresa): `B0199200001`…`B0199200501`.

## Envío DGII

Ningún modelo `justech.do.dgii.60x.exporter` en el registry.  
Flag `dgii_reports` = True (feature flag) ≠ exporter instalado.

`DGII_EXTERNAL_SUBMISSION = NOT_PERFORMED`  
`FORMAT_GENERATION` oficial = NOT_INSTALLED  
`DATA_EXTRACT` (JSON QA) = PASS — `DX_TEST_606/607/608_202608.json`

Tras el extracto, los moves TEST tienen `justech_do_include_in_dgii = False` y motivo de exclusión, para no contaminar un 607 real de agosto.

## 608 workflow

Wizard `justech.do.ncf.void.wizard` + `action_void_ncf` sobre PIN `B0199100102` y `B0199100104`, motivo `04`, observación DX TEST. Residual contable intacto (como diseña el wizard).

## e-CF / 609 / IR-17 / IT-1

NOT_INSTALLED / NOT_APPLICABLE en este registry.
