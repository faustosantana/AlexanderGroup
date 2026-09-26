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
- Repo branch at closeout start: `cursor/doralex-golive-baseline-86c5`
- Parent commit: `e078d3f5e00ec2ccfdd9252b90720477d44048b2`
- Secrets: none stored in this baseline
