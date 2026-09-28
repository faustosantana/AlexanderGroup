# 01 — Repro: crear producto con una sola empresa

Usuario: Fausto, switcher solo **Inversiones Doralex**.
Producto: Licencia Windows Server. ITBIS 18% puesto automático.

Error: `El impuesto seleccionado pertenece a otra empresa.`

Causa: el producto es compartido. Al guardar, el overlay copia el 18%
equivalente a las otras 5 empresas y ese segundo write volvía a pasar
por el guardia con el switcher en una sola empresa.

No es un impuesto mal elegido por el usuario.
