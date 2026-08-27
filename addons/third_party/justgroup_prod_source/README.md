# Justgroup PROD source snapshot (code only)

**Freeze source:** Justgroup PROD `justgroup-vps` `/usr/lib/odoo/custom-addons`  
**Freeze ID reference:** `JUSTECH_PROD_GOLDEN_2026_08_27`  
**Copied:** 2026-08-27 — NO business data, NO filestore, NO secrets.

## Status

- Read-only extract from Justgroup for Doralex reuse evaluation.
- Not auto-installed on Doralex DEV/PROD from this folder until hygiene + install plan pass.
- Enterprise addons were **not** copied (`ENTERPRISE_BLOCKED`).
- Modules NOT copied (examples): `justech_dgcp_bridge`, e-CF stack, payroll stack, `justech_managed_services`.

## Adaptations applied in this tree

- `justech_admin_center`: secret file paths overridable via env
  `JUSTECH_ADMIN_CENTER_PASSWORD_HASH_FILE` / `JUSTECH_ADMIN_CENTER_PASSWORD_INCOMING_FILE`.

## Next

See `docs/migration/JUSTGROUP_MODULE_CLASSIFICATION.md` for ACTION matrix.
