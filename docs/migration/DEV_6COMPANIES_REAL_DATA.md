# Doralex DEV — Datos reales de las 6 empresas (Levantamiento oficial)

> Fecha: 2026-08-28. Fuente: **Excel oficial** `Levantamiento_Basico_Odoo_Alexander_Group`
> + 6 logos. Solo **DEV**. PROD intacto. No se cargaron históricos/balances/asientos.
> Las compañías provisionales (ids 28–33) fueron **actualizadas** con datos reales
> (no se crearon duplicados). Datos sensibles (números de cuenta, cédulas) quedan
> **solo en Odoo DEV** (no se versionan por privacidad).

## Backups

Pre-carga: `dev_20260828_110913`; post-carga: `dev_20260828_111325` (verificados).

## 6 empresas reales (companies 28–33)

| id | Razón social | RNC | Representante legal | Logo |
| -- | ------------ | --- | ------------------- | ---- |
| 28 | INVERSIONES DORALEX,S.RL. | 1-32-22011-2 | Alexander Piña Aquino | Doralex ✅ |
| 29 | COMERCIALIZADORA DE ALIMENTOS PIÑARIA, S.R.L. | 1-32-27106-8 | Alba Rafaelina Arias Mora | CAP ✅ |
| 30 | DOMINION BUSINESS,S.R.L. | 1-32-72150-2 | Arisleydi Contreras Suero | Dominion ✅ |
| 31 | INVERSIONES EL MAYUMA, S.R.L. | 1-32-71015-2 | Eldris Marlenny Ramirez Minaya | El Mayuma ✅ |
| 32 | REMPART GROUP S.R.L. | 1-32-76915-5 | Agustin Ventura Alcantara | Rempart ✅ |
| 33 | BLUE ELITE, S.R.L. | 1-33-37126-1 | Geilin Rosario Suero | Blue Elite ✅ |

Por empresa: moneda **DOP**, país **DO**, dirección fiscal, provincia/municipio,
teléfono, correo, tipo de contribuyente (Persona jurídica), actividad principal y
fecha de inicio cargados. Datos legales adicionales (rep. legal, cédula, tipo,
actividad, fecha, nombre comercial, RNC) guardados en el `comment` del partner de
cada compañía. **Logos: 6/6 asignados** (todos identificados con certeza — sin
`PENDING_LOGO_MAPPING`).

Configuración técnica **preservada** por empresa: chart `do` (289 cuentas),
37 impuestos, 8 diarios, 11 posiciones fiscales, 1 almacén, secuencias, reglas
multiempresa. `provisional_leftover = 0`.

## Cuentas bancarias

**6 cuentas** creadas (todas **BANRESERVAS**, DOP), vinculadas al partner de cada
compañía y a su diario de banco. Titular = representante legal. Números de cuenta y
cédulas del titular **no se versionan** (solo en Odoo DEV).

- **Balances iniciales**: `PENDING_OPENING_BALANCE_POSTING` — registrados en el
  Excel pero **NO** contabilizados (no se creó asiento de apertura).
- **Fechas de balance** (`05//08/2026` en el Excel): `PENDING_DATE_VALIDATION` —
  formato inconsistente, **no corregido/inventado**.

## Usuarios

Única persona en la hoja "Usuarios": **ALEXANDER PIÑA AQUINO** (aparece en las 6
empresas). Se creó **1 solo usuario** (sin duplicados), login
`inversionesdoralex@gmail.com`, `default_company = 28`, `allowed_company_ids = las 6`.
Cargo/área/supervisor/nivel de acceso están **vacíos** en el Excel → grupos
funcionales `PENDING_USER_ROLE` (asignado grupo interno base). Contraseña la define
el usuario (no se fija).

## Sucursales / almacenes

Hoja "Sucursales": 1 "Oficina principal" por empresa (misma dirección fiscal,
responsable = rep. legal). No hay almacenes adicionales → se **reutilizó** el
almacén técnico existente por empresa (renombrado "Oficina principal - <empresa>"),
sin duplicar.

## NCF / DGII

Hoja "Datos fiscales" **vacía** (sin rangos NCF autorizados). → `NCF_CONFIG =
PENDING_REAL_RANGES`. Estructura fiscal instalada (23 `l10n_latam.document.type` +
11 `justech.do.fiscal.document.type`); **no** se inventaron secuencias ni se emiten
comprobantes reales.

## Config Doralex

`web.base.url = https://dev.doralexgroup.cloud`, `mail.catchall.domain =
doralexgroup.cloud` (sin editar vendor).

## Validaciones (0 FAIL / 0 ERROR / 0 CRITICAL)

- 6 empresas reales, 0 provisionales duplicadas, cada una con RNC + logo + diarios
  + impuestos + almacén + secuencias + cuenta bancaria correcta; 1 usuario sin duplicar.
- **Aislamiento 36/36**, golden **9/9**, six-company **6/6**, repo **15/15**.
- Company switching (usuario con las 6 compañías) y aislamiento multiempresa OK.
- **Runtime errors = 0** (se limpiaron bundles de assets web obsoletos que
  generaban `FileNotFound`; regenerados). `dev`/`prod` = 200. PROD intacto.

## Estado

`COMPANY_MASTER_DATA = PASS` · `COMPANY_LEGAL_DATA = PASS` · `COMPANY_LOGOS = PASS`
(6/6) · `BANK_ACCOUNTS = PASS` · `BANK_OPENING_BALANCES = PENDING_POSTING` ·
`USERS_IMPORT = PASS` (roles `PENDING_USER_ROLE`) · `WAREHOUSE_BRANCH_CONFIG = PASS` ·
`ACCOUNTING_RD_CONFIG = PASS` · `NCF_CONFIG = PENDING_REAL_RANGES` ·
`MULTICOMPANY_CONFIG = PASS` · `COMPANY_ISOLATION_TEST = 36/36` ·
`DORALEX_DEV_RUNTIME_ERRORS = 0` · `READY_FOR_MASTER_DATA_LOAD = YES` ·
`READY_FOR_OPENING_BALANCES = YES` (estructura lista; falta autorizar el asiento) ·
`READY_FOR_FULL_DORALEX_DATA_LOAD = NO` (faltan NCF DGII, catálogo ampliado,
maestros masivos, roles de usuarios, y Enterprise).
