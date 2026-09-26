# 03 — Validación de gates (antes de escribir)

## Rangos autorizados

| Empresa | Next in range | Next = last+1 |
| --- | --- | --- |
| Doralex | 152 ∈ 141–160 | 152 = 151+1 |
| El Mayuma | 113 ∈ 109–118 | 113 = 112+1 |
| Rempart | 112 ∈ 106–113 | 112 = 111+1 |

## Histórico vs autorización

| Empresa | MAX_REAL Odoo | Last autorizado | Next autorizado existe | Decisión |
| --- | --- | --- | --- | --- |
| Doralex | 151 | 151 | NO | APPLY (idéntico) |
| El Mayuma | 110 | 112 | NO | APPLY — hueco 111–112 no está en Odoo; avanzar next a 113 evita colisión |
| Rempart | 110 | 111 | NO | APPLY — hueco 111 no está en Odoo; avanzar next a 112 evita colisión |

Hard-stop solo si `MAX_REAL > last_autorizado` (Odoo iría atrás) o si el next
ya existe en posted/draft/cancelled/consumo. Ningún hard-stop disparó.

## Prefijo

`next_ncf_display` nativo = `{prefix}{next:08d}`. Se escribe `next_sequence`
entero (152 / 113 / 112), nunca un número suelto de otra serie. Prefijo B15
sale del `document_type_id`.

## No consumo

Auditoría e inspect solo leen. No se llama `next_by_id` / `next_by_code` /
`consume_next`. No se crean facturas.
