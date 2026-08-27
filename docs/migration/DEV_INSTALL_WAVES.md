# Doralex DEV — Instalación por olas (WAVE A/B/C) de módulos migrados

> Fecha: 2026-08-27. Fuente: `addons/third_party/justgroup_prod_source/` (24 módulos,
> code-only, migrados por el agente local desde Justgroup). Target: **Doralex DEV**.
> PROD **no** tocado. Sin `-u all`. Sin datos de Justech.

## Pre-check (FASE 2)

- **Secrets scan**: `validate_repository.py` → **0 secretos reales**. Los 107
  "hallazgos" del heurístico eran definiciones de campo (`fields.Char`), generadores
  seguros (`secrets.token_urlsafe`), lecturas `os.environ`/`context.get` y fixtures
  de test. Se excluyó el código vendorizado (`addons/third_party/`) del heurístico
  de palabra-clave (se mantiene la detección de bloques de clave privada). Verificado
  a mano: sin literales de credencial.
- **Higiene** (`scan_module_hygiene.py`): hallazgos benignos (nombres de modelo
  `justech.*`, website del autor en manifest, VAT de test). Sin hardcodes de
  credencial.
- **Bug corregido en `.gitignore`**: la regla `data/` (para filestore runtime)
  excluía los `data/` de los módulos Odoo. Corregido a `/data/` (root). Esto NO
  recupera los archivos ya perdidos en el commit `e42a08c` (nunca se commitearon);
  requiere que el agente local **re-commitee** los `data/` ahora que la regla está
  arreglada.
- **Limpieza**: 234 archivos AppleDouble `._*` (basura de tar en macOS) eliminados.

## Olas de instalación

### WAVE A — Community-safe (instaladas en DEV)

| Módulo | Estado |
| ------ | ------ |
| `justech_core` | installed |
| `bi_convert_purchase_from_sales` | installed |
| `multi_invoice_manual_payment_prod` | installed |
| `justech_accounting_recovery` | installed |
| `justech_quotation_client_dedup` | installed |
| `justech_sale_purchase_trace` | installed |

Post-install: `dev /web/health` = 200 (healthy estable), **0 runtime errors**,
golden env **9/9**, 6-company **6/6** (evidencia en `evidence/`).

### WAVE B — Requiere adaptación (bloqueadas: migración incompleta)

`justech_l10n_do_base`, `justech_l10n_do_ncf`, `justech_fiscal_admin`,
`justech_vendor_bill_po_control`, `justech_l10n_do_adel_freeze`, más varias de
Wave A tail (`justech_report_identity_guard`, `justech_sale_terms_guard`,
`justech_purchase_sale_margin_control`, `justech_approval_flow`, `justech_warranty`,
`justech_global_audit_log`, `l10n_do_accounting`) **no** instalables **todavía**:
les faltan archivos `data/*.xml`/`.csv` en el repo (excluidos por el bug `.gitignore`).

### WAVE C — Enterprise-blocked (no instalar)

`justech_l10n_do_payments_withholding`, `justech_l10n_do_reports`,
`justech_l10n_do_treasury` → dependen de `account_accountant`/`accountant`
(**Enterprise**). Doralex es Community → `BLOCKED_BY_ENTERPRISE_SOURCE`.

### NOT_APPLICABLE / HOLD

`justech_modules`, `justech_admin_center` (plataforma interna Justech de
licencias/admin), `justech_security_ux` (dep `justech_ecf_core` ausente + Enterprise).

## Blocker real restante (accionable por el agente LOCAL)

15 de 24 módulos tienen sus `data/` **ausentes en el repo** por el bug de
`.gitignore` (ya corregido). Para completar Wave B se necesita **re-commit desde el
agente local** (que tiene el código en disco / acceso a Justgroup): con la regla ya
arreglada, `git add addons/third_party/justgroup_prod_source/**/data/**` + push.
Luego, desde Doralex, se instalan dirigidos en DEV. **No** se pueden reconstruir
esos `data/` aquí sin inventarlos (contienen tipos de documento fiscal, secuencias,
crons, catálogos).

## Reglas respetadas

Sin `-u all`; instalación dirigida por módulo con rollback; PROD intacto; sin datos
de Justech; sin reconstruir Enterprise; sin copiar el árbol Enterprise de Justgroup.
