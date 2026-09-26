# 01 — System info

- Date: 2026-09-26
- Host: Doralexgroup (2.25.121.111)
- OS: Ubuntu 24.04.4 LTS, kernel 6.8.0-138-generic
- CPU: 2 vCPU (AMD EPYC 9354P)
- RAM: 7.8 Gi
- Disk: 96G, 15% used (14G / 83G free)
- Odoo: 19.0-20260324 Enterprise image `doralex-odoo-enterprise:19.0.20260324`
- Python (container): 3.12.3
- PostgreSQL: 16.15
- Domains: `doralexgroup.cloud` (Prod), `dev.doralexgroup.cloud` (Dev)
- Prod DB: `doralex_prod` / container `doralex-production-odoo`
- Staging DB: `doralex_ent_staging` / container `doralex-enterprise-staging-odoo`
- Custom addons path (container): `/mnt/custom-addons` (host bind `/opt/doralex/production/custom-addons`)
- Enterprise addons path: `/mnt/enterprise`
- Base module version in image: 19.0.1.3
- Repo branch: `cursor/doralex-golive-baseline-86c5`
- CURRENT_GIT_COMMIT: `585042508262e575a156f53ad8528b25ea8e2949`
- Parent commit: `e078d3f5e00ec2ccfdd9252b90720477d44048b2`
- Secrets: none stored in this baseline

## CUSTOM_MODULE_VERSIONS (installed)

- justech_alexander_base 19.0.1.0.15
- justech_alexander_ux 19.0.1.6.8
- justech_alexander_reports 19.0.3.13.7
- justech_alexander_admin 19.0.1.0.1
- justech_alexander_website 19.0.1.0.8
- justech_alexander_microsoft_mail 19.0.1.0.6
- justech_approval_flow 19.0.1.3.8
- justech_l10n_do_base 19.0.1.27.1
- justech_l10n_do_ncf 19.0.2.31.0
- justech_l10n_do_payments_withholding 19.0.1.7.2 (FROZEN)
- justech_l10n_do_reports 19.0.1.24.8
- justech_purchase_sale_margin_control 19.0.8.29.38 (FROZEN)
- justech_sale_purchase_trace 19.0.1.2.11
- multi_invoice_manual_payment_prod 19.0.1.5.4 (FROZEN)
- justech_global_audit_log 19.0.4.1.4
- justech_fiscal_admin 19.0.1.10.0
- l10n_do 19.0.2.0
- l10n_do_accounting 19.0.1.0.1
