# Inventario y clasificación de módulos (Justgroup → Doralex)

> Fecha: 2026-08-27. **JUSTGROUP_AUDIT = PASS** (acceso SSH real a Justgroup PROD).

## Acceso verificado

| Check | Result |
|-------|--------|
| `ssh justgroup-vps` | PASS (`hostname=justgroup`, `odoo=active`) |
| Odoo | 19.0-20260324 |
| DB | `justech` (PostgreSQL 16.15) |
| addons_path | community + **enterprise** + `/usr/lib/odoo/custom-addons` |
| Custom modules on disk | 44 |
| Installed total | 360 (Community 173 / Enterprise 142 / Justech custom 41 / …) |
| Golden freeze | `/opt/odoo-backups/prod-golden-baseline-20260827_182451` |

## Matriz completa

Ver **[`JUSTGROUP_MODULE_CLASSIFICATION.md`](JUSTGROUP_MODULE_CLASSIFICATION.md)**.

## Código copiado (sin datos)

`addons/third_party/justgroup_prod_source/` — 24 módulos (code-only).

## Doralex DEV install

**BLOCKED en este entorno local Justgroup:** falta `~/.ssh/doralex_ed25519` y el puerto 22 de `2.25.121.111` respondió `Connection refused` tras el probe. HTTP `https://dev.doralexgroup.cloud` = 200.

Cuando el agente Doralex / esta máquina tengan `ssh doralex-server`, instalar por waves A→B→C del classification doc (**nunca** `-u all`, **nunca** PROD primero).


## Canonical GitHub source (2026-08-27)

See [`CANONICAL_ADDONS_SOURCE.md`](CANONICAL_ADDONS_SOURCE.md) and https://github.com/faustosantana/odoo-custom-addons
