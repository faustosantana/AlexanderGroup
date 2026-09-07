# 11 — Usuarios, roles, multiempresa, seguridad

Alexander **no** se duplicó. Un solo login multiempresa.

| USER | LOGIN | ACTIVE | DEFAULT_COMPANY | ALLOWED_COMPANIES | SALES | PURCHASE | ACCOUNTING | INVENTORY | ADMIN | PORTAL | STATUS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Administrator | admin | YES | BLUE ELITE | 8–13 | YES | YES | YES | YES | YES | NO | IMPLEMENTER |
| Alexander Piña Aquino | inversionesdoralex@gmail.com | YES | DORALEX | 8–13 | YES | YES | YES | YES | NO | NO | OPERATIONAL_OK |
| DX TEST USER SECURITY BLU | dx.test.security@justech.do | YES | BLUE ELITE | 8 | YES | NO | NO | NO | NO | NO | QA_LEFTOVER |
| Fausto Santana | fausto@justech.do | YES | DORALEX | 1+8–13 | YES | YES | YES | YES | YES | NO | IMPLEMENTER |

`USERS_TOTAL = 4`
`USERS_WITH_EXCESSIVE_PERMISSIONS = 1` (usuario QA activo). Settings de admin/fausto = implementación, no se quitó.

## Roles propuestos (NO asignados a ciegas)

Administrador / Gerencia / Ventas / Compras / Contabilidad / CxC / CxP / Inventario / Consulta.

Hoy solo existe Alexander como usuario de negocio. Queda configurado con ventas+compras+contabilidad+inventario, sin Settings, 6 compañías. Matriz de personas adicionales = pendiente de confirmación (17).

## Record rules

| TEST | SEEN | FOREIGN |
|---|---|---|
| user 7 solo company 8 | 2 (QA Blue Elite) | 0 |
| Alexander context company 11 | 22 | 0 |

`CROSS_COMPANY_DATA_LEAK = 0`

## QA en prod (identificar, no borrar a ciegas)

- 12 partners `DX TEST CLIENTE/PROVEEDOR … — NO FISCAL REAL` + partner security
- 14 invoices/refunds NCF 9910/9911 posteadas
- pagos `PBNK1/2026/*` y bills QA
- user `dx.test.security@justech.do`

Staging DXQA-OPREADY no está en prod.

## Otros

- Compañía 1 no se archivó (`TECHNICAL_COMPANY_SAFE_TO_ARCHIVE = NO`).
- Website no se tocó.
- No se permitió ni se cambió la política de borrado de facturas posteadas.
- Justgroup no se usó como fuente de datos comerciales.
