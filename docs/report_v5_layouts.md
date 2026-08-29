# V5 — 6 sistemas de composición (cotización)

`VISUAL_V5 = PENDING`. No autoaprobado. Solo cotizaciones en este corte.

| COMPANY | LAYOUT_ID | HEADER_STRUCTURE | TITLE_POSITION | LOGO_POSITION | CLIENT_STRUCTURE | META_STRUCTURE | TOTALS_STYLE | SIGNATURE_STYLE | VISUALLY_DISTINCT |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DOR | `dor` / `dx_header_doralex` + `dx_sale_doralex` | rail naranja + marca apilada (logo→razón→RNC→contacto) | derecha del masthead, con meta debajo | grande, izquierda, sobre la razón social | bloque horizontal abierto bajo el masthead | 2×2 bajo el título (en header) | panel derecho sin caja, total naranja | dos rayas, spacer blanco | YES (si silueta lo confirma) |
| PIN | `pin` / `dx_header_pinaria` + `dx_sale_pinaria` | logo centrado + razón + RNC·tel·email + banda verde | cuerpo, izquierda | centro arriba | abierto bajo título/meta | 2×2 a la derecha del título (cuerpo) | derecho, total rojo sello | dos rayas, spacer blanco | YES |
| DOM | `dom` / `dx_header_dominion` + `dx_sale_dominion` | logo+legal a la izquierda; rail vertical de título a la derecha | rail derecho del header | pequeño/medio, izquierda | bloque flotante 58% | stack vertical flotante 42% | derecho, total naranja | dos rayas, spacer blanco | YES |
| MAY | `may` / `dx_header_mayuma` + `dx_sale_mayuma` | logo ancho + 2 líneas chicas; título con regla | derecha del header, con raya teal | grande, centro-izquierda | bloque amplio abierto | una fila FECHA VALIDEZ VENDEDOR MONEDA | derecho, regla teal | dos rayas, spacer blanco | YES |
| REM | `rem` / `dx_header_rempart` + `dx_sale_rempart` | solo marca + línea azul (sin título) | cuerpo, arriba derecha, serif grande | izquierda, con marca debajo | 60% abierto | 40% labels chicos / valores grandes | derecho, azul | dos rayas, spacer blanco | YES |
| BLU | `blu` / `dx_header_blueelite` + `dx_sale_blueelite` | título+legal a la izquierda; logo a la derecha | izquierda del header | arriba derecha | 62% asimétrico | 38% escalonado | derecho, navy/cyan | dos rayas, spacer blanco | YES |

Spacer: PNG blanco. `SIGNATURE_SPACER_VISIBLE` debe ser FAIL si reaparece gris.
