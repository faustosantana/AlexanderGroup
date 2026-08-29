# Paleta real de logos (DEV, V4 — 2026-08-29)

Muestreo de `res.company.logo` y de los PNG oficiales de Dominion / El Mayuma.
No se recolorean logos. No se inventan hex de ciclos anteriores.

| COMPANY | LOGO_SOURCE | PRIMARY | SECONDARY | ACCENT | LOGO_ASSET_OK |
| --- | --- | --- | --- | --- | --- |
| DOR | `res.company.logo` DOR.png (engranaje naranja + negro) | `#E46018` | `#1A1A1A` | `#E46018` | PASS (asset previo, sin placa) |
| PIN | `res.company.logo` PIN.png (sello rojo + hoja verde) | `#30A83C` | `#C00000` | `#C00000` | PASS (asset previo, sin placa) |
| DOM | PNG oficial Dominion Business (círculos naranja/teal, fondo blanco→alpha) | `#50B0B0` | `#F09040` | `#F09040` | PASS tras reemplazo (antes FAIL: wordmark negro / placa) |
| MAY | PNG oficial El Mayuma (casas + wordmark negro + teal, crop + alpha) | `#1A1A1A` | `#54B4A8` | `#54B4A8` | PASS tras reemplazo (antes FAIL: placa negra) |
| REM | `res.company.logo` REM.png (edificios negros + iconos azul) | `#1A1A1A` | `#3048A8` | `#3048A8` | PASS (asset previo, sin placa) |
| BLU | `res.company.logo` BLU.png (navy + diamante cian) | `#243C9C` | `#18B4F0` | `#18B4F0` | PASS (asset previo, sin placa) |

`LOGO_ASSET_OK` es un gate de render sobre papel blanco. Dominion y El Mayuma
quedan FAIL hasta que el PNG correcto esté en `res.company.logo` y el header
no use placa oscura.

Layout V4 (no es solo recolor):

- DOR: acento vertical naranja + título grande + una regla
- PIN: línea verde suave + título serif, sin banda rellena
- DOM: logo sobre blanco + título teal + regla naranja
- MAY: logo ancho sobre blanco + tracking arquitectónico + regla teal
- REM: serif institucional + regla fina
- BLU: cian sutil + título navy, sin losa rellena
