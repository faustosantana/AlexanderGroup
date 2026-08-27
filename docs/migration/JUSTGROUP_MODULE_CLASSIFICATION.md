# Justgroup → Doralex — Module Classification Matrix

**Date:** 2026-08-27  
**JUSTGROUP_ACCESS:** PASS (`ssh justgroup-vps`)  
**Source:** PROD read-only (`justech` / `/usr/lib/odoo/custom-addons`)  
**Odoo:** 19.0-20260324 Enterprise path present (142 enterprise modules installed)  
**PostgreSQL:** 16.15  
**Companies (Justgroup):** 4  
**Studio:** installed (DB-only customizations — **not** copied)  

**DORALEX install:** BLOCKED in this environment — `~/.ssh/doralex_ed25519` missing; SSH `2.25.121.111:22` connection refused after probe. HTTP DEV/PROD = 200.

## Runtime metadata (Justgroup)

| Item | Value |
|------|------:|
| Installed modules (all) | 360 |
| Enterprise installed | 142 |
| Custom on disk | 44 |
| Cron | 84 |
| Server actions | 311 |
| Automated actions | 15 |
| Groups | 189 |
| ACL | 2355 |
| Record rules | 638 |
| Reports | 88 |
| Mail templates | 80 |
| Sequences | 136 |

## Classification legend

| Flag | Meaning |
|------|---------|
| REQUIRED | Needed for Doralex RD multiempresa baseline |
| OPTIONAL | Useful, not blocking go-live |
| REQUIRES_ADAPTATION | Copy OK; hardcodes/deps need work before install |
| NOT_APPLICABLE | Justech/JAIOS/product-specific |
| ENTERPRISE_BLOCKED | Needs legitimate Enterprise source/license — do not copy from Justgroup enterprise tree |

## Matrix (custom / third-party)

| MODULE | SOURCE | VERSION | PURPOSE | DEPENDENCIES (key) | REQUIRED | OPTIONAL | REQUIRES_ADAPTATION | NOT_APPLICABLE | ENTERPRISE | HARDCODES | MULTICOMPANY_RISK | ACTION |
|--------|--------|---------|---------|-------------------|---------|----------|---------------------|----------------|------------|-----------|-------------------|--------|
| l10n_do_accounting | Justgroup custom | 19.0.1.0.1 | Adel DO fiscal / NCF base | l10n_do, account_debit_note | YES | | | | NO | clean | LOW | **REQUIRED** — copied |
| justech_l10n_do_base | Justgroup custom | 19.0.1.27.1 | RNC padrón / fiscal UX | l10n_do_accounting, account | YES | | YES | | NO | domain/db strings | MED | **REQUIRES_ADAPTATION** — copied |
| justech_l10n_do_ncf | Justgroup custom | 19.0.2.31.0 | NCF Justech stack | base+ncf deps + bi_convert | YES | | YES | | partial | domain | HIGH | **REQUIRES_ADAPTATION** — copied |
| justech_l10n_do_adel_freeze | Justgroup custom | 19.0.1.0.0 | Freeze Adel vs Justech NCF | ncf, l10n_do_accounting | | YES | YES | | NO | domain | MED | OPTIONAL — copied |
| justech_accounting_recovery | Justgroup custom | 19.0.1.4.0 | Accounting recovery helpers | account | | YES | YES | | NO | domain | MED | OPTIONAL — copied |
| bi_convert_purchase_from_sales | third_party | 19.0.0.0 | SO→PO convert | sale, purchase, stock | | YES | | | NO | clean | LOW | OPTIONAL — copied |
| justech_sale_purchase_trace | Justgroup custom | 19.0.1.2.10 | Sale/purchase traceability | sale/purchase/stock + bi_convert | | YES | YES | | NO | domain | MED | OPTIONAL — copied |
| justech_purchase_sale_margin_control | Justgroup custom | 19.0.8.29.38 | Margins / cost coverage | sale, purchase, stock, account | | YES | YES | | NO | domain/url | HIGH | OPTIONAL — copied |
| justech_approval_flow | Justgroup custom | 19.0.1.3.8 | PO/SO/invoice approvals | sale, purchase, account | | YES | YES | | NO | domain/url | HIGH | OPTIONAL — copied |
| multi_invoice_manual_payment_prod | Justgroup custom | 19.0.1.5.4 | Multi-invoice payment wizard | account | | YES | | | NO | clean | MED | OPTIONAL — copied |
| justech_l10n_do_payments_withholding | Justgroup custom | 19.0.1.7.2 | Payments + withholdings RD | **account_accountant**, ncf, reports | | YES | YES | | **YES** | domain | HIGH | REQUIRES_ADAPTATION + Enterprise accountant |
| justech_l10n_do_reports | Justgroup custom | 19.0.1.24.8 | Fiscal reports | **accountant**, ncf | | YES | YES | | **YES** | domain/url | MED | REQUIRES_ADAPTATION + Enterprise |
| justech_l10n_do_treasury | Justgroup custom | 19.0.1.6.7 | Treasury UX | accountant + payments | | YES | YES | | **YES** | domain | MED | REQUIRES_ADAPTATION + Enterprise |
| justech_fiscal_admin | Justgroup custom | 19.0.1.10.0 | Fiscal admin settings | ncf stack | | YES | YES | | NO | domain | MED | REQUIRES_ADAPTATION — copied |
| justech_vendor_bill_po_control | Justgroup custom | 19.0.3.6.2 | Vendor bill ↔ PO control | ncf | | YES | YES | | NO | domain | MED | OPTIONAL — copied |
| justech_warranty | Justgroup custom | 19.0.1.9.1 | Warranty | core, sale, account | | YES | YES | | NO | db strings | MED | OPTIONAL — copied |
| justech_core | Justgroup custom | 19.0.1.0.0 | Core helpers | base | | YES | YES | | NO | domain | LOW | OPTIONAL — copied |
| justech_global_audit_log | Justgroup custom | 19.0.4.1.4 | Global audit | base | | YES | YES | | NO | url | LOW | OPTIONAL — copied |
| justech_quotation_client_dedup | Justgroup custom | 19.0.1.0.0 | Quotation partner dedup | sale | | YES | YES | | NO | url | LOW | OPTIONAL — copied |
| justech_report_identity_guard | Justgroup custom | 19.0.1.0.0 | Report identity guard | sale/account/stock | | YES | YES | | NO | url | LOW | OPTIONAL — copied |
| justech_sale_terms_guard | Justgroup custom | 19.0.1.0.0 | Sale terms guard | sale_management | | YES | YES | | NO | url | LOW | OPTIONAL — copied |
| justech_modules | Justgroup custom | 19.0.1.8.7 | Module platform / admin keys | base, mail | | YES | YES | | NO | email/domain | HIGH | REQUIRES_ADAPTATION — copied |
| justech_admin_center | Justgroup custom | 19.0.2.12.1 | Admin console | modules, fiscal_admin | | YES | YES | | NO | secret_path/domain | HIGH | REQUIRES_ADAPTATION — copied (path env) |
| justech_security_ux | Justgroup custom | 19.0.4.1.9 | Security UX / roles | many justech_* + **ecf_core** | | | YES | | NO | domain | HIGH | REQUIRES_ADAPTATION — copied; **blocked install until ecf or dep trimmed** |
| justech_dgcp_bridge | Justgroup custom | 19.0.1.3.1 | JAIOS/DGCP | crm, sale | | | | YES | NO | — | — | **NOT_APPLICABLE** — not copied |
| justech_ecf_* | Justgroup custom | various | e-CF DGII | ecf stack | | | YES | | NO | — | HIGH | NOT copied (phase 2) |
| justech_*_hr_payroll* | Justgroup custom | various | Payroll RD | **hr_payroll Enterprise** | | | YES | | **YES** | — | HIGH | **ENTERPRISE_BLOCKED** path — not copied |
| justech_managed_services | Justgroup custom | 19.0.2.1.3 | MS product | website, subscription | | | | YES | NO | — | — | **NOT_APPLICABLE** — not copied |
| justech_mail_outgoing_policy | Justgroup custom | 19.0.1.2.0 | Outgoing mail policy | helpdesk | | YES | YES | | NO | — | MED | not copied (phase 2) |
| justech_recurring_fee | Justgroup custom | 19.0.1.2.0 | Recurring fees | sale_subscription | | YES | YES | | NO | — | MED | not copied (phase 2) |
| studio_hotfix | Justgroup custom | 19.0.1.0.2 | Studio helper | web | | | | | **YES** (Studio) | — | — | ENTERPRISE_BLOCKED companion — not copied |
| /usr/lib/odoo/enterprise/* | Enterprise | — | Odoo Enterprise apps | — | | | | | **YES** | — | — | **ENTERPRISE_BLOCKED** — do not copy |

## Copied into repo

Path: `addons/third_party/justgroup_prod_source/` (**24 modules**, ~15MB code).

## Install waves (Doralex DEV only — when SSH available)

1. **Wave A (Community-safe):** `l10n_do_accounting`, `multi_invoice_manual_payment_prod`, `bi_convert_purchase_from_sales`, `justech_core`, `justech_global_audit_log`, guards/dedup, then `justech_sale_purchase_trace`, `justech_approval_flow`, `justech_purchase_sale_margin_control`.
2. **Wave B (Fiscal Justech):** `justech_l10n_do_base` → `justech_l10n_do_ncf` → vendor bill / adel freeze — after hardcode pass.
3. **Wave C (Enterprise-gated):** payments/withholding, reports, treasury — only if Doralex has licensed `account_accountant` / `accountant`.
4. **Never:** DGCP/JAIOS, payroll without Enterprise HR, copying Enterprise tree from Justgroup.

## Explicit non-goals

- No Justech business data / filestore / users / credentials.
- No Doralex PROD install until DEV = 0 FAIL / 0 ERROR / 0 CRITICAL.
- No `-u all`.
