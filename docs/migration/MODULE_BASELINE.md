# Doralex DEV — Module Baseline (antes de cargar datos)

> Fecha: 2026-08-27. Entorno: **DEV** (`doralex_dev`), Odoo 19.0-20260817.
> Objetivo: dejar DEV con los **módulos estándar correctos, instalados y probados**
> antes de cargar datos de Alexander Group. **No** se cargaron Excel/datos.

## Backup previo (obligatorio)

`scripts/backup.sh dev` → `/opt/doralex/backups/dev/dev_20260827_163526`
(**verificado**, SHA256). Realizado antes de instalar módulos.

## Instalación (targeted, sin `-u all`, sin demo)

Comando: `odoo -d doralex_dev -i <lista> --stop-after-init --without-demo=all`.

| Módulo estándar (REQUIRED) | Estado |
| -------------------------- | ------ |
| `contacts` | installed |
| `mail` | installed |
| `calendar` | installed |
| `crm` | installed |
| `sale_management` | installed |
| `purchase` | installed |
| `stock` | installed |
| `account` | installed |
| `l10n_do` (localización RD) | installed |
| `hr` | installed |
| `hr_holidays` | installed |

Total módulos instalados (con dependencias): **90**. Evidencia:
[`evidence/dev_installed_modules.txt`](evidence/dev_installed_modules.txt).

## Salud post-instalación

- `https`/loopback `dev /web/health` → **200** (`{"status":"pass"}`), contenedor **healthy**.
- Runtime log tras arranque: **0 ERROR / 0 CRITICAL** (evidencia
  [`evidence/dev_runtime_errors.txt`](evidence/dev_runtime_errors.txt), vacío).

## Baseline contable (estándar, sin catálogo ampliado)

Evidencia [`evidence/dev_accounting_baseline.txt`](evidence/dev_accounting_baseline.txt):

- `account_account` = **51** (cuentas estándar por defecto).
- `account_journal` = **7** (diarios base).
- `account_tax` = **4** (impuestos estándar).
- `res_company` = **1** (compañía por defecto; aún **no** las 6 de Alexander).

> Se instaló el **módulo** `l10n_do` (código de localización RD disponible). **No**
> se cargó el catálogo ampliado de Alexander ni la configuración fiscal final por
> empresa (eso viene con los Excel). Conocer estas 51 cuentas estándar evita
> duplicados al cargar el catálogo.

## Enterprise (no disponible)

Ausentes en la imagen Community → `BLOCKED_BY_ENTERPRISE_SOURCE`:
`web_studio`, `documents`, `sign`, `account_accountant`. (`spreadsheet_dashboard`
base sí está presente en Community.) La arquitectura ya es enterprise-ready:
al llegar la licencia se instalan sin reconstruir (ver
[`../infrastructure/ENTERPRISE_READINESS.md`](../infrastructure/ENTERPRISE_READINESS.md)).

## Higiene / multiempresa

`tools/scan_module_hygiene.py` disponible para escanear módulos custom antes de
copiarlos (company_id fijo, refs Justech, emails/URLs/RNC hardcodeados). Sobre
`custom-addons` (vacío) → **OK** (evidencia
[`evidence/hardcode_scan.txt`](evidence/hardcode_scan.txt)). Aún no hay módulos
custom porque falta acceso a Justgroup (ver `JUSTGROUP_MODULE_INVENTORY.md`).

## Resultado

`MODULE_BASELINE_PASS = YES` para el **baseline estándar** en DEV.
Los módulos custom reutilizables de Justgroup quedan **pendientes de acceso**
(`JUSTGROUP_ACCESS_REQUIRED`) — no bloquean el baseline estándar.

## Producción

**No** se instalaron módulos custom nuevos en PROD ni se cargó nada de Alexander.
PROD permanece con base + healthy.
