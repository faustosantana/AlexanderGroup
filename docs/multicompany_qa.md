# Multicompañía QA

Fuente de verdad: `document.company_id`. Nunca la compañía activa del usuario.

## Aislamiento fiscal

Prueba crítica: usuario/contexto **Blue Elite** + factura **Rempart** `B0199004001`.

- NCF banda REM (`99004xxx`)
- Compose PDF NCF = NCF del move Rempart
- `company_id` del move = REM

`MULTICOMPANY_FISCAL_ISOLATION = PASS`

El motor bloquea `consume_next` si `move.company_id != range.company_id`.

## Diarios / impuestos / bancos

Cada empresa tiene diarios Ventas / Compras / Banreservas / Caja propios.  
ITBIS 18% por `company_id`.  
Cuentas Banreservas distintas (no se compartieron diarios).

## Usuarios

| Usuario | Compañías | Fiscal / NC |
| --- | --- | --- |
| Administrator | — | Administrador Fiscal + Can create Fiscal Credit Notes |
| ALEXANDER PIÑA AQUINO | 6/6 | **sin** grupos fiscales — no puede emitir NC |

`MULTICOMPANY_REPORT_ISOLATION = PASS` en compose. UI wizard cross-company: NOT_TESTED esta corrida.
