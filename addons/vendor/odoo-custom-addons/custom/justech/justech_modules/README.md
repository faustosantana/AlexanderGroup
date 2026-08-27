# Justech Modules

Platform licensing engine for Justech ERP (F31.1 → F31.1.5).

**Version:** 19.0.1.5.0 — Platform closed, API v1 frozen.

## Public API — version 1

Stable contract: `justech.license.service.API_VERSION = 1`

```python
service = env["justech.license.service"]
service.get_api_version()          # → 1
service.is_active("platform_core")
service.require_active("dgii_reports")
service.get_activation_catalog(company=env.company)  # F31.1.5
service.activate_module("hellenia_pos", company=env.company)
service.deactivate_module("hellenia_pos", company=env.company)
```

## Module Activation Wizard

**Menu:** Justech → Licencias → Module Activation  
Uses public API only — no Odoo install/uninstall. See `docs/JUSTECH_WIZARD_ACTIVATION_GUIDE.md`.

## Manifest registration

All production modules declare `justech_register` in `__manifest__.py`.  
Bulk sync on post_init via `register_all_installed_manifests()`.

## DEV install (product module only)

```bash
odoo-bin -d hellenia_dev -u justech_modules --test-enable --stop-after-init \
  --test-tags=/justech_modules
```

Evidence: `evidence/f31-1-5-platform-final/`
