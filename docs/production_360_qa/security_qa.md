# Seguridad QA

| Check | Resultado |
| --- | --- |
| admin (`__system__` / uid admin) 6 compañías + group_system | PASS |
| `fausto@justech.do` como login | NOT_CONFIGURED |
| Operacional `inversionesdoralex@gmail.com` 6/6, no system | PASS |
| Usuario QA `dx.test.security@justech.do` solo BLU no ve factura DOR | PASS |
| Recuperación Contable no implícita en operacional | PASS |

Contraseña del usuario QA de seguridad: solo en el servidor (no en Git). El usuario está catalogado (id 7) para borrarse en cleanup.

Crons activos (sin habilitar nada destructivo): Graph inbound, garantías vencidas, audit retención, alertas NCF.
