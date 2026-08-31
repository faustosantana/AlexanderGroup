# Auditoría Excel Alexander vs Doralex staging

Fecha: 2026-08-31  
Fuente Excel: `Levantamiento_Basico_Odoo_Alexander_Group.xlsx` (idéntico al `(1).xlsx`)  
Hojas: Instrucciones, Empresas, Cuentas bancarias, Sucursales y almacenes, Usuarios, Datos fiscales  
Entorno leído: **solo staging** `doralex_ent_staging` (`127.0.0.1:8269`)  
`PROD_TOUCHED = NO` · `CONFIG_CHANGED = NO` · datos **no** cargados

`ALEXANDER_EXCEL_AUDITED = YES`

El Excel es la fuente de verdad de lo **ya entregado**. No se vuelve a pedir
RNC, dirección, banco ni número de cuenta.

---

## Scorecard

```
COMPANIES_IN_EXCEL = 6
COMPANIES_MATCHED = 6
COMPANY_FIELDS_MISSING = 12
  (6× provincia no mapeada a state_id + 6× fecha inicio no escrita en
   l10n_do_dgii_start_date; los valores YA están en el Excel)

BANK_ACCOUNTS_IN_EXCEL = 6
BANK_ACCOUNTS_MATCHED = 6
BANK_FIELDS_MISSING = titular persona vs compañía; tipo Corriente/Ahorros
  no tipificado; balance inicial NO contabilizado; fecha 05//08/2026

BRANCHES_IN_EXCEL = 6
BRANCHES_MATCHED = 6
  (oficina = dirección fiscal; Odoo tiene 1 Almacén Principal técnico/empresa)

USER_ROWS_IN_EXCEL = 6
ODOO_ALEXANDER_USERS = 1
USER_DUPLICATION_STATUS = NO_DUPLICATES
  (misma persona, 6 allowed companies — modelo correcto ya aplicado)

FISCAL_ROWS_IN_SOURCE_EXCEL = 0

NCF_CURRENTLY_CONFIGURED = B01 + B04 × 6 empresas DO (12 rangos)
NCF_SOURCE_CONFIRMED = QA_CONFIGURATION
  (create_uid=__system__, 2026-08-29, series 99100xxx / 99110xxx)
  NO vino del Excel.

DATA_ALREADY_SUPPLIED_COUNT = 28
DATA_STILL_REQUIRED_COUNT = 16
```

---

## 1. Empresas (Excel vs Odoo)

Odoo IDs: 11 Doralex · 9 Piñaria · 10 Dominion · 12 El Mayuma · 13 Rempart · 8 Blue Elite.

| COMPANY | FIELD | EXCEL_VALUE | ODOO_VALUE | STATUS |
|---|---|---|---|---|
| INVERSIONES DORALEX,S.RL. | razón social | INVERSIONES DORALEX,S.RL. | INVERSIONES DORALEX,S.RL. | MATCH |
| INVERSIONES DORALEX,S.RL. | nombre comercial | INVERSIONES DORALEX,S.RL. | oficial = misma; `dx_trade_name` = Doralex | MATCH_NORMALIZED |
| INVERSIONES DORALEX,S.RL. | RNC | 1-32-22011-2 | 132220112 | MATCH_NORMALIZED |
| INVERSIONES DORALEX,S.RL. | tipo de contribuyente | Persona jurídica | `l10n_do_dgii_tax_payer_type` = taxpayer | MATCH_NORMALIZED |
| INVERSIONES DORALEX,S.RL. | actividad principal | SERVICIO, COMERCIO, AGRARIO, INDUSTRIAL | Inversiones, comercio, agroindustria e industria | MATCH_NORMALIZED |
| INVERSIONES DORALEX,S.RL. | dirección fiscal | AV. SAN VICENTE DE PAUL, NO. 115, LOS MINA | igual | MATCH |
| INVERSIONES DORALEX,S.RL. | provincia | SANTO DOMINGO | *(vacío — `state_id` no cargado)* | MISSING_IN_ODOO |
| INVERSIONES DORALEX,S.RL. | municipio | SANTO DOMINGO ESTE | SANTO DOMINGO ESTE (`city`) | MATCH |
| INVERSIONES DORALEX,S.RL. | teléfono | 849-207-5817 | 849-207-5817 | MATCH |
| INVERSIONES DORALEX,S.RL. | correo | inversionesdoralex@gmail.com | administracion@inversionesdoralex.com | DIFFERENT |
| INVERSIONES DORALEX,S.RL. | representante legal | Alexander Piña Aquino | `dx_legal_representative` igual | MATCH |
| INVERSIONES DORALEX,S.RL. | cédula representante | 223-0157134-9 | `dx_legal_id_number` igual | MATCH |
| INVERSIONES DORALEX,S.RL. | moneda | DOP | DOP | MATCH |
| INVERSIONES DORALEX,S.RL. | fecha inicio operaciones | 2020-11-02 | `l10n_do_dgii_start_date` vacío | MISSING_IN_ODOO |

Las otras 5 empresas siguen el **mismo patrón** (RNC normalizado sin guiones; representante y cédula en `dx_*`; municipio en `city`; provincia vacía; fecha inicio vacía; correo UX `administracion@…`).

| COMPANY | RNC Excel | RNC Odoo | Tel | Rep. legal | Cédula | Correo Excel | Correo Odoo | Dir. |
|---|---|---|---|---|---|---|---|---|
| PIÑARIA | 1-32-27106-8 | 132271068 | MATCH | Alba Rafaelina Arias Mora | 280-103907-0 | piñariascomercializadora@gmail.com | administracion@pinariagroup.com | MATCH_NORMALIZED (coma final) |
| DOMINION | 1-32-72150-2 | 132721502 | MATCH | Arisleydi Contreras Suero | 402-4200332-1 | dominionsrl@hotmail.com | administracion@dominion-business.com | MATCH |
| EL MAYUMA | 1-32-71015-2 | 132710152 | MATCH | Eldris Marlenny Ramirez Minaya | 402-4218015-2 | inversioneselmayuma@gmail.com | administracion@elmayuma.com | MATCH_NORMALIZED (`ll`→`II`) |
| REMPART | 1-32-76915-5 | 132769155 | MATCH | Agustin Ventura Alcantara | 402-2314668-5 | rempartsrl@hotmail.com | administracion@rempartgroup.com | MATCH |
| BLUE ELITE | 1-33-37126-1 | 133371261 | MATCH | Geilin Rosario Suero | 402-1097505-4 | bluelitesrl@hotmail.com | administracion@blueelite.net | MATCH |

**No pedir de nuevo** razón social, RNC, dirección, actividad, teléfono, representante ni cédula.  
El correo DIFFERENT es overlay UX vs Gmail/Hotmail del Excel: **confirmación de cuál usar**, no re-captura.

---

## 2. 7.ª compañía

```
TECHNICAL_TEMPLATE_COMPANY = Plantilla técnica (no operativa)
COMPANY_ID = 1
currency = USD
country = US
HAS_TRANSACTIONS = YES (166 posted; QA / plantilla, no operación DO)
HAS_FISCAL_CONFIG = NO (0 rangos NCF)
HAS_USERS = YES (1: ux.qa.staging@doralex.local la tiene entre allowed)
RECOMMENDATION = KEEP
```

No está en el Excel. No eliminar. Decisión de Alexander: ¿queda inactiva / sin fiscal DO? Eso sí va en la solicitud (una pregunta, no datos maestros).

---

## 3. Cuentas bancarias

Las 6 filas del Excel están en `res.partner.bank` (números coinciden). Diario Banreservas por empresa.

| COMPANY | BANK | ACCOUNT_NUMBER | ACCOUNT_TYPE | CURRENCY | HOLDER (Excel) | INITIAL_BALANCE | BALANCE_DATE | ODOO_JOURNAL | MATCH_STATUS |
|---|---|---|---|---|---|---|---|---|---|
| DORALEX | BANRESERVAS | 9604436830 | Corriente | DOP | Alexander Piña Aquino | 5,000,000 | 05//08/2026 | Banco Banreservas · DOR | MATCH (número/banco/moneda) |
| PIÑARIA | BANRESERVAS | 9604097492 | Corriente | DOP | Alba Rafaelina Arias Mora | 2,450,000 | 05//08/2026 | Banco Banreservas · PIN | MATCH |
| DOMINION | BANRESERVAS | 9605588726 | **Ahorros** | DOP | Arisleydi Contreras Suero | 1,500,000 | 05//08/2026 | Banco Banreservas · DOM | MATCH |
| EL MAYUMA | BANRESERVAS | 9605543104 | Corriente | DOP | Eldris Marlenny Ramirez Minaya | 3,000,000 | 05//08/2026 | Banco Banreservas · MAY | MATCH |
| REMPART | BANRESERVAS | 9608739498 | Corriente | DOP | Agustin Ventura Alcantara | 4,600,000 | 05//08/2026 | Banco Banreservas · REM | MATCH |
| BLUE ELITE | BANRESERVAS | 9608670542 | Corriente | DOP | Geilin Rosario Suero | 1,250,000 | 05//08/2026 | Banco Banreservas · BLU | MATCH |

Titular en Odoo = partner de la **compañía** (no la persona). Tipo Odoo = `bank` (no Corriente/Ahorros).  
Balances del Excel: **`PENDING_OPENING_BALANCE_POSTING`** (0 asientos de apertura).  
Fecha Excel `05//08/2026`: formato roto; **no inventar** 5 ago vs 8 may.

**No pedir de nuevo** banco, número, tipo, titular, RNC/cédula titular, moneda.

---

## 4. Config bancaria que NO está en el Excel

| BANK_ACCOUNT | BANK_GL_ACCOUNT | OUTSTANDING_RECEIPTS | OUTSTANDING_PAYMENTS | INBOUND | OUTBOUND | DGII | CLASSIFICATION |
|---|---|---|---|---|---|---|---|
| Banreservas · DOR/PIN/DOM/MAY/REM/BLU | cuenta “Bank” (código vacío en chart DO) | asignada QA (nombre Outstanding Receipts; código vacío) | Outstanding Payments QA | Manual Payment | Manual Payment | *(vacío)* | NEEDS_ACCOUNTANT_CONFIRMATION |
| Plantilla US · Bank | 101401 | 101403 | 101404 | Manual Payment | Manual Payment | n/a | NEEDS_ACCOUNTANT_CONFIRMATION (no operativa) |

Cuentas Outstanding **existen** en el plan (QA). No crear otras sin el contador.  
Forma DGII (01/02/03…) **no** está en el Excel ni en el diario Banreservas.

---

## 5. Sucursales / almacenes

Excel: **solo 6 oficinas principales** (misma dirección fiscal, responsable = rep. legal).

Odoo: 1 `stock.warehouse` “Almacén Principal” por empresa (DOR/PIN/DOM/MAY/REM/BLU) + 1 ubicación interna. No hay almacenes adicionales de Alexander.

Inconsistencia interna del Excel (no re-preguntar): hoja Empresas pone provincia=SANTO DOMINGO / municipio=SDE; hoja Sucursales las **invierte**.

**No pedir** de nuevo esas direcciones.  
**Sí preguntar** si existen almacenes/bodegas reales distintos de la oficina (cantidades, no la dirección ya dada).

---

## 6. Usuarios

```
EXCEL_ROWS = 6
excel_person = ALEXANDER PIÑA AQUINO
ODOO_USER_COUNT (internos activos) = 5
ALEXANDER_USER_IDS = [5]
LOGINS = inversionesdoralex@gmail.com
DEFAULT_COMPANY = 11 INVERSIONES DORALEX,S.RL.
ALLOWED_COMPANIES = 8,9,10,11,12,13
DUPLICATES = NO
```

Los 6 correos del Excel son **correos de empresa**, no 6 personas. Ya se modeló 1 usuario + 6 compañías.  
Cargo / área / supervisor / nivel de acceso: **vacíos en el Excel**.  
Otros logins (admin, Fausto, UX QA, dx.test) son Justech/QA, no Alexander.

---

## 7. Datos fiscales del Excel

```
FISCAL_ROWS_IN_SOURCE_EXCEL = 0
```

Solo encabezados. Alexander **no** entregó en este archivo: tipos NCF, primer/último autorizado, último usado, vencimiento, e-CF.

---

## 8. NCF actuales en Odoo — origen

| COMPANY | NCF_TYPE | RANGE_START | RANGE_END | CURRENT_NEXT | EXPIRATION | SOURCE |
|---|---|---|---|---|---|---|
| Doralex | B01 | 99100001 | 99100050 | 99100048 | — | QA_CONFIGURATION |
| Doralex | B04 | 99110001 | 99110050 | 99110017 | — | QA_CONFIGURATION |
| Piñaria | B01 | 99100101 | 99100150 | 99100150 | — | QA_CONFIGURATION |
| Piñaria | B04 | 99110101 | 99110150 | 99110112 | — | QA_CONFIGURATION |
| Dominion | B01 | 99100201 | 99100250 | 99100248 | — | QA_CONFIGURATION |
| Dominion | B04 | 99110201 | 99110250 | 99110212 | — | QA_CONFIGURATION |
| El Mayuma | B01 | 99100301 | 99100350 | 99100348 | — | QA_CONFIGURATION |
| El Mayuma | B04 | 99110301 | 99110350 | 99110312 | — | QA_CONFIGURATION |
| Rempart | B01 | 99100401 | 99100450 | 99100448 | — | QA_CONFIGURATION |
| Rempart | B04 | 99110401 | 99110450 | 99110412 | — | QA_CONFIGURATION |
| Blue Elite | B01 | 99100501 | 99100550 | 99100548 | — | QA_CONFIGURATION |
| Blue Elite | B04 | 99110501 | 99110550 | 99110512 | — | QA_CONFIGURATION |

`create_uid = __system__` · `create_date = 2026-08-29 15:34:03` (cutover Enterprise).  
Series `9910xxxx` = placeholder QA. **No son rangos DGII de Alexander.**

---

## 9. Contaminación QA (no es dato Alexander)

| Tag / patrón | Conteo staging |
|---|---|
| Partners `DXQA` | 14 |
| Partners `DX TEST` / `DX-QA-FINAL` | 6 clientes + 7 proveedores (todos “NO FISCAL REAL”) |
| Productos DXQA | 7 |
| SO `DXQA*` | 47 (`DXQA-MASS-20260831` = 15, `DXQA-FINAL` = 31) |
| Clientes/proveedores reales Alexander | **0** |

Cualquier CxC/CxP/producto residual de QA **no** cuenta como maestro real.

---

## 10. Bloques A–P

| Bloque | ALREADY_CONFIGURED | SOURCE | COMPLETE | NEEDS_ALEXANDER |
|---|---|---|---|---|
| A. NCF reales | QA B01/B04 only | QA_CONFIGURATION | NO | YES |
| B. Outstanding | asignado QA (nombres) | QA_CONFIGURATION | NO | YES (confirmación contador) |
| C. Plan de cuentas | 1779 cuentas l10n_do | ODOO_L10N_DO | NO (falta visto bueno) | YES (confirmar, no rehacer) |
| D. Impuestos / retenciones | 226 taxes; **0** withholding configs | ODOO_L10N_DO | NO | YES si hay retenciones reales; si no, 623 sigue N/A |
| E. Clientes | solo DX TEST / DXQA | QA | NO | YES |
| F. Proveedores | solo DX TEST / DXQA | QA | NO | YES |
| G. Productos | DXQA + 6 códigos técnicos | QA | NO | YES |
| H. CxC abiertas reales | no | QA invoices | NO | YES si migran saldos |
| I. CxP abiertas reales | no | QA bills | NO | YES si migran saldos |
| J. Anticipos / créditos | no | — | NO | YES si existen |
| K. Balance de apertura | 0 asientos; Excel sí trajo 6 balances banco | ALEXANDER_EXCEL (montos) + no posted | NO | YES: **autorizar asiento** y aclarar fecha `05//08/2026` |
| L. Inventario | 8 quants ≠0 (técnico/QA) | UNKNOWN/QA | NO | YES si hay stock real |
| M. Activos | 0 | — | NO | YES si hay AF |
| N. Usuarios / permisos | 1 usuario Alexander sin roles | ALEXANDER_EXCEL_PARTIAL | NO | YES: roles + si hay más personas |
| O. Almacenes extra | 1 WH técnico/empresa | EXCEL oficinas only | NO | YES solo si hay más locales |
| P. Histórico a migrar | no | — | NO | YES (sí/no + corte) |

---

## 11. Matriz final

| DATA_ITEM | ALREADY_IN_EXCEL | ALREADY_IN_ODOO | MATCH | NEEDS_CONFIRMATION | MUST_REQUEST_FROM_ALEXANDER |
|---|---|---|---|---|---|
| Razón social ×6 | YES | YES | YES | NO | **NO** |
| RNC ×6 | YES | YES | NORMALIZED | NO | **NO** |
| Dirección fiscal / oficina ×6 | YES | YES | YES | NO | **NO** |
| Actividad | YES | YES | NORMALIZED | NO | **NO** |
| Teléfono empresa | YES | YES | YES | NO | **NO** |
| Correo empresa (Gmail/Hotmail) | YES | overlay UX distinto | NO | **cuál correo es el oficial** | NO (no reescribir) |
| Representante + cédula | YES | YES | YES | NO | **NO** |
| Moneda DOP | YES | YES | YES | NO | **NO** |
| Fecha inicio ops | YES | NO (campo vacío) | — | cargar desde Excel | **NO** |
| Provincia | YES | NO (`state_id`) | — | mapear desde Excel | **NO** |
| Banco + número + tipo + titular | YES | número/banco YES | YES | titular persona vs compañía | **NO** |
| Balance inicial banco | YES | NO posted | — | **fecha + autorizar asiento** | YES (autorización, no el monto) |
| Oficinas principales | YES | vía compañía | YES | NO | **NO** |
| Usuario Alexander | YES (6 filas) | 1 user / 6 cos | YES | roles | roles YES |
| NCF / e-CF / vigencia | **NO** | QA B01/B04 | NO | — | **YES** |
| Outstanding / GL banco / forma DGII | **NO** | QA parcial | NO | contador | **YES** |
| Clientes / proveedores / productos reales | **NO** | QA only | NO | — | **YES** |
| CxC/CxP/anticipos/TB/inventario/AF/histórico | **NO** | QA only | NO | si migran | **YES** |
| Destino plantilla USD | **NO** | id=1 KEEP | — | — | **YES** (decisión) |

---

## 12. Listas

### ALREADY_SUPPLIED_BY_ALEXANDER

1. Seis razones sociales y nombres  
2. Seis RNC  
3. Tipo de contribuyente (persona jurídica)  
4. Actividad principal  
5. Direcciones fiscales  
6. Provincia / municipio (aunque Odoo no mapeó `state_id`)  
7. Teléfonos  
8. Correos Gmail/Hotmail de cada empresa  
9. Representantes legales y cédulas  
10. Moneda DOP  
11. Fechas de inicio de operaciones  
12. Seis cuentas BANRESERVAS (número, tipo, moneda)  
13. Titular y cédula/RNC de cada cuenta  
14. Flag activa = Sí  
15. Seis balances iniciales y la fecha tal como la escribieron (`05//08/2026`)  
16. Seis oficinas principales (dirección + responsable + teléfono)  
17. Una persona usuaria: Alexander Piña Aquino, asociada a las seis empresas, con esos correos  
18. Logos (entrega previa, no esta hoja)

### STILL_REQUIRED_FROM_ALEXANDER

Solo lo que **no** está en el Excel y **no** es dato QA:

1. Rangos NCF/e-CF reales (tipos que usarán, autorización, desde/hasta, próximo, vencimiento)  
2. ¿e-CF el día 1?  
3. Primer período 606/607/608 a declarar en el sistema  
4. Confirmación del contador: cuenta GL banco + outstanding cobros/pagos (propuesta QA no es definitiva)  
5. Formas de pago DGII reales (01/02/03…) y si hay caja/chequera extra  
6. Visto bueno del plan de cuentas / diarios (no rehacer el catálogo)  
7. Retenciones ISR/ITBIS **si existen**; si no, dejar 623 N/A  
8. Clientes reales (no DXQA)  
9. Proveedores reales  
10. Productos/servicios reales  
11. Si migran historia: TB de corte, CxC/CxP abiertas, anticipos  
12. Autorizar asiento de los 6 balances banco del Excel + aclarar `05//08/2026`  
13. Inventario real / almacenes **adicionales** (no reenviar la oficina)  
14. Activos fijos si hay  
15. Roles de Alexander y si hay **más personas** (el Excel no trajo cargo/nivel)  
16. ¿La plantilla USD (compañía 1) se archiva o se deja inactiva?

---

`READY_FOR_ALEXANDER_DATA_LOAD` sigue en YES a nivel de motor.  
Esta auditoría **reduce** la solicitud: no molestar con RNC/dirección/banco/cuenta.
