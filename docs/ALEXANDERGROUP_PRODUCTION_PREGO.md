# Alexander Group / Doralex — PRE-GO FINAL

> **SUPERSEDED 2026-09-16.** El deploy autorizado se ejecutó. Informe único:
> [`ALEXANDERGROUP_PRODUCTION_DEPLOY.md`](ALEXANDERGROUP_PRODUCTION_DEPLOY.md)
> — **FINAL STATUS: SUCCESS**. Este PRE-GO queda como evidencia previa (PROD no tocado *entonces*).

Fecha: 2026-09-16.
**PROD TOUCHED: NO** (este documento). Post-deploy: ver informe SUCCESS.

---

## PRE-GO FINAL

ITBIS 16 SALE PROD: **MISSING** en 8–13 (purchase sí existe). El `-u` de overlay **no** lo crea. Receta de clon del 18% venta de la misma empresa: documentada, no ejecutada.
TRACE FILE/DB MISMATCH: **SAFE TO LEAVE FROZEN**
DX ACCOUNT UNIQUENESS: **PASS** (114/114 `candidates=1`, 0 foreign)
NCF OPERABILITY MATRIX: código no bloqueado; operaciones fiscales por compañía restringidas (ver matriz)
APPROVAL FLAGS AFTER UPDATE: sale/po/inv **False** en las 6 compañías (migración UX 19.0.1.6.0). Histórico conservado.
DGII PADRON: OFF · CRON OFF · ROWS 0 · PARTNER/INVOICE BLOCK NO
EMAIL: CONFIGURATION PASS · LIVE SEND = post-deploy controlled test
DEPLOY ENV VARS: `HOST=db` · `USER=doralex_prod` · `PASSWORD` SET · `PORT=5432`
BACKUP FREE SPACE: 83G libres · estimado ~80M · margen PASS
ROLLBACK ORDER: plan corregido (stop + drain PG **antes** de restore). `restore.sh` actual no drena conexiones y el `docker exec` de filestore corre con Odoo ya stopped.
PROD TOUCHED: **NO**

HARD BLOCKERS:

1. ITBIS 16% SALE ausente en las 6 compañías. El deployment autorizado de tres módulos no lo crea. Sin este impuesto, el GO de venta 16% queda bloqueado.

OPERATIONAL WARNINGS:

- NCF: PIN/DOM B01 y B11 EXPIRED; DOR B11 EXPIRED; MAY/REM B11 y B13 EXPIRED; BLU B15 EXHAUSTED; DOR B04 y B13 con 1 número; B17 MISSING en todas.
- Traza: DB last-upgrade `19.0.1.2.11` vs código montado `19.0.1.2.10` (solo manifiesto; archivos de código/vistas idénticos).
- `web.base.url` = http.
- microsoft_mail permanece 19.0.1.0.4.
- Backup fresco aún no existe (intencional hasta autorización).

READY FOR HUMAN GO: **NO**

---

## 1. ITBIS 16% DE VENTA EN PROD

Auditoría READ-ONLY. 0 productos con 16% venta. STAGING sí tiene venta 16% (ids 461–466) — **no copiar esos ids**.

| COMPANY | 16% PURCHASE EXISTS | 16% SALE EXISTS | SALE TAX NAME | TAX GROUP | ACCOUNTS | REPARTITION | TAGS | ACTION REQUIRED |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BLU 8 | YES (`16% ITBIS` id 238 purchase) | **NO** | — | ITBIS (group 87) | — | — | — | CREATE SALE clone of 18% (id 235) |
| PIN 9 | YES (id 276) | **NO** | — | ITBIS (101) | — | — | — | CREATE SALE clone of 18% (id 273) |
| DOM 10 | YES (id 314) | **NO** | — | ITBIS (115) | — | — | — | CREATE SALE clone of 18% (id 311) |
| DOR 11 | YES (id 352) | **NO** | — | ITBIS (129) | — | — | — | CREATE SALE clone of 18% (id 349) |
| MAY 12 | YES (id 390) | **NO** | — | ITBIS (143) | — | — | — | CREATE SALE clone of 18% (id 387) |
| REM 13 | YES (id 428) | **NO** | — | ITBIS (157) | — | — | — | CREATE SALE clone of 18% (id 425) |

18% SALE estructural (misma empresa, no STAGING):

- name `18% ITBIS` · `type_tax_use=sale` · `amount=18` · `amount_type=percent` · `price_include=False`
- group `ITBIS` de **esa** compañía
- invoice/refund: base 100% (sin cuenta, tag `base.18%`) + tax 100% → cuenta `ITBIS on Sale of Goods` **solo** de esa compañía (tags `tax.18%`)
- cuentas venta (exclusivas): 8→1883, 9→2171, 10→2459, 11→2747, 12→3035, 13→3323

Tags `base.16%` (id 12) y `tax.16%` (id 17) **ya existen** en PROD (país DO). No hace falta crear tags.

### Qué NO crea el `-u` autorizado

`justech_alexander_{base,ux,reports}` no contienen XML/Python que cree `16% ITBIS` sale. El 16% de STAGING fue **configuración UAT**, no migración.

### Receta de configuración (NO EJECUTAR)

Por cada compañía 8–13, **sin** `copy()` de STAGING y **sin** ids de STAGING:

1. Tomar el `18% ITBIS` **sale** de esa misma `company_id`.
2. Crear (cuando se autorice) un impuesto nuevo:
   - name: `16% ITBIS`
   - company_id: la misma
   - type_tax_use: `sale`
   - amount: `16.0`
   - amount_type: `percent`
   - price_include: `False`
   - include_base_amount: `False`
   - tax_group_id: el `ITBIS` de esa compañía
   - invoice/refund: base 100% + tax 100% a `ITBIS on Sale of Goods` de esa compañía
   - tags: `base.16%` / `tax.16%` (ids PROD 12 / 17)
3. `active=True`
4. **No** asignar a `product.template.taxes_id` ni a categorías.

Hasta que esta receta se autorice y ejecute, ITBIS 16% SALE no queda disponible. **HARD BLOCKER.**

---

## 2. SALE_PURCHASE_TRACE VERSION MISMATCH

| Fuente | Valor |
| --- | --- |
| Código cargado ahora | `/mnt/custom-addons/justech_sale_purchase_trace` |
| Manifest montado | **19.0.1.2.10** (mtime 2026-08-30T04:30:58Z) |
| `get_manifest()` / `installed_version` (label «Latest Version») | 19.0.1.2.10 |
| `latest_version` (label «Installed Version» = último `-u` en DB) | 19.0.1.2.11 |
| Copia en imagen `/usr/lib/odoo/custom-addons/...` | 19.0.1.2.11 (addons_path **después** de `/mnt`) |
| `diff -rq` mount 1.2.10 vs runtime 1.2.11 | **solo `__manifest__.py`** |

Causa: el bind-mount Alexander (30-ago) reescribió el nombre/versión a 1.2.10 y quitó la línea de changelog 1.2.11 (ocultar botones en factura). Las vistas y el Python son **idénticos**. La DB recuerda el último upgrade como 1.2.11.

Dependencia Alexander: `justech_alexander_ux` `depends` incluye `justech_sale_purchase_trace`. El `-u` propuesto **no** nombra traza; Odoo no la actualiza.

Restart posterior: recarga **1.2.10** (mismo path que lleva 8 días corriendo). No hay campo/modelo/vista extra en 1.2.11 que falte en 1.2.10. Riesgo AttributeError/vista faltante: **no observado**.

Clasificación: **SAFE TO LEAVE FROZEN**. No `-u` traza. No tocarla.

---

## 3. DX ACCOUNT UNIQUENESS

Filtro: `company_ids in [company]` + `name` + `account_type=liability_non_current`.
`DXMAP_FAILS 0`. Ninguna cuenta compartida.

Muestra: cada regla tiene exactamente 1 id por compañía (p. ej. BLU `DX-ISR-PROF-PF-15` → 1897; DOR `DX-ITBIS-30-PJ` → 2749). El overlay no elige «la primera coincidencia» de un set >1.

RESULT: **PASS**. No BLOCKER.

---

## 4. POST-DEPLOY FISCAL OPERABILITY BY COMPANY

El `-u` no crea ni copia rangos. QA `991*` cancelados: no usar.

| COMPANY | B01 | B04 | B11 | B13 | B15 | B17 | OPERACIONES DISPONIBLES | OPERACIONES BLOQUEADAS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BLU 8 | READY | READY | READY | READY | EXHAUSTED | MISSING | ventas B01; NC B04; informal emitido B11; gastos menores B13; bills **recibidas** | B15 emitido; B17 exterior |
| PIN 9 | EXPIRED | READY | EXPIRED | READY | READY | MISSING | NC B04; gastos menores B13; B15; bills recibidas | ventas B01; informal B11; B17 |
| DOM 10 | EXPIRED | READY | EXPIRED | READY | READY | MISSING | NC B04; gastos menores B13; B15; bills recibidas | ventas B01; informal B11; B17 |
| DOR 11 | READY | READY (1) | EXPIRED | READY (1) | READY | MISSING | ventas B01; **una** NC B04; **un** B13; B15; bills recibidas | informal B11; B17; NC/B13 extra |
| MAY 12 | READY | READY | EXPIRED | EXPIRED | READY | MISSING | ventas B01; NC B04; B15; bills recibidas | informal B11; gastos menores B13; B17 |
| REM 13 | READY | READY | EXPIRED | EXPIRED | READY | MISSING | ventas B01; NC B04; B15; bills recibidas | informal B11; gastos menores B13; B17 |

Bills proveedor **recibidas** (NCF del vendor): **NOT REQUIRED** rango de la compañía.

Ninguna compañía se presenta como habilitada para una operación cuyo rango no esté READY.

---

## 5. APPROVALS

Hoy 8–13: `sale_appr=True` `po_appr=True` `inv_appr=True`.
Param overlay ya False. 1 request + 6 rules se conservan.

El `-u justech_alexander_ux` 19.0.1.4.0 → 19.0.1.6.0 ejecuta
`migrations/19.0.1.6.0/end-apply_catalog.py` → `apply_approval_overlay` →
`_apply_approval_company_config`: escribe False en las 6 compañías operativas
(tokens BLUE ELITE / PIÑARIA / DOMINION / DORALEX / MAYUMA / REMPART).
No borra requests, rules, chatter ni desinstala `justech_approval_flow`.

Tras update: APPROVAL FLOW ACTIVE: **NO** en Ventas, Compras y Facturación.
`SALES CONFIRM BLOCKED BY APPROVAL: NO`.

---

## 6. ROLLBACK — ORDEN CORREGIDO (PLAN, no ejecución)

`/opt/doralex/scripts/restore.sh` (leído en el host):

1. `verify_backup.sh` **con Odoo todavía arriba**
2. `docker stop doralex-production-odoo`
3. `pg_restore --clean` **sin** comprobar que no queden backends `odoo-*` en `doralex_prod`
4. `docker exec` al contenedor **ya stopped** para extraer filestore (`|| err` — puede fallar en silencio)
5. `docker start`
6. **No** restaura `custom-addons`

Eso **no** es «restore DB → luego stop» (el stop va antes del dump restore). Tampoco cumple drain de conexiones ni filestore fiable.

### Plan aprobado (NO EJECUTAR)

```bash
BACKUP=/opt/doralex/backups/prod/pre_alexander_release_YYYYMMDD_HHMMSS

# 1) mantenimiento (proxy / anuncio)
# 2) detener Odoo
docker stop doralex-production-odoo

# 3) cero conexiones Odoo a doralex_prod
docker exec doralex-production-db bash -lc \
  "psql -U doralex_prod -d doralex_prod -c \"SELECT pid, usename, application_name, state FROM pg_stat_activity WHERE datname='doralex_prod' AND pid <> pg_backend_pid();\""
# si quedan odoo-*: SELECT pg_terminate_backend(pid) ... AND application_name LIKE 'odoo%'

# 4) verificar backup
bash /opt/doralex/scripts/verify_backup.sh "${BACKUP}"
docker exec -i doralex-production-db pg_restore --list < "${BACKUP}/db.dump" | head

# 5) restaurar DB (Odoo ya down, sin backends odoo)
docker exec -i doralex-production-db pg_restore -U doralex_prod -d doralex_prod --clean --if-exists \
  < "${BACKUP}/db.dump"

# 6) filestore sobre el volumen (contenedor stopped: no usar docker exec)
#    extraer a un tmp y copiar al volume doralex_prod_odoo_data, o
docker start doralex-production-odoo && sleep 2
docker exec -i doralex-production-odoo sh -c 'rm -rf /var/lib/odoo/filestore && tar xzf - -C /var/lib/odoo' \
  < "${BACKUP}/filestore.tar.gz"
docker stop doralex-production-odoo

# 7) custom-addons / versión
tar xzf "${BACKUP}/custom-addons.tar.gz" -C /opt/doralex/production

# 8) arrancar
docker start doralex-production-odoo

# 9) logs / registry
# 10) smoke
```

No usar `restore.sh` a secas como procedimiento aprobado de este release.

---

## 7. DEPLOY ENV VARS (READ-ONLY)

Dentro de `doralex-production-odoo`:

| Variable | Valor | Destino |
| --- | --- | --- |
| `HOST` | `db` | servicio Compose `db` = `doralex-production-db` en `doralex_prod_net` |
| `USER` | `doralex_prod` | rol PostgreSQL / `POSTGRES_USER` |
| `PASSWORD` | SET (no se imprime) | `POSTGRES_PASSWORD` del `.env` |
| `PORT` | `5432` | puerto interno |

Comando real — **NO EJECUTAR**:

```bash
docker exec -u 100:101 doralex-production-odoo bash -lc \
  'python3 /usr/bin/odoo -d doralex_prod --db_host="$HOST" --db_port="${PORT:-5432}" --db_user="$USER" --db_password="$PASSWORD" \
   -u justech_alexander_base,justech_alexander_ux,justech_alexander_reports \
   --stop-after-init --no-http'
```

No usar `-u all`.

---

## 8. ESPACIO DE BACKUP

| Item | Valor |
| --- | --- |
| filesystem | `/dev/sda1` ext4 96G |
| free | **83G** (14% used) |
| DB size | 196 MB |
| last `db.dump` | 20M |
| filestore vivo | 63M · last tar 22M |
| custom-addons | 24M · last tar 7.4M |
| estimated total fresco | **~80M** |
| safety (fresco + copia rollback + operación) | ~200M << 83G |

Hay espacio. No se inicia backup en este turno.

---

## 9. EMAIL

EMAIL CONFIGURATION: **PASS** (Graph + mailbox por empresa; SMTP=0).
EMAIL LIVE SEND: **POST-DEPLOY CONTROLLED TEST**.
No es blocker.

---

## CIERRE

READY FOR HUMAN GO: **NO**

Causa dura: ITBIS 16% SALE no existe y el `-u` de tres módulos no lo crea.

Cuando se autorice el impuesto 16% venta (receta §1) **y** el backup fresco, este documento se reevalúa. Hasta entonces: DETENERSE.

PROD TOUCHED: NO
