# Canonical addons source (Doralex)

## SOURCE OF TRUTH

`https://github.com/faustosantana/odoo-custom-addons` (private)

AlexanderGroup must **not** become a second editable source.

## Cloud Agent limitation

Cursor Cloud Agents for this product repo receive a GitHub App token scoped to **AlexanderGroup only**.
They cannot clone or read `odoo-custom-addons` even when the App has “All repositories”.

## Delivery strategy (chosen)

**Regenerable vendored snapshot** committed into this repo:

```
addons/vendor/odoo-custom-addons/
```

- Generated from canonical Wave A + Wave B only
- Provenance in `ORIGIN_REF.json` (commit + tags)
- **Do not edit** module trees under vendor/
- Regenerate from a machine with access to both repos:

```bash
CANONICAL_PATH=/path/to/odoo-custom-addons \
  bash tools/sync_odoo_custom_addons_vendor.sh
```

Cloud Agents consume `addons/vendor/odoo-custom-addons` only — no extra credentials.

## Waves

See vendored `WAVES.json` and canonical `docs/DORALEX_COMPATIBILITY.md`.

| Wave | Meaning |
|------|---------|
| WAVE_A | Community-safe baseline for Doralex DEV |
| WAVE_B | Needs fiscal/config adaptation; code vendored |
| WAVE_C | Enterprise-blocked — remains only in canonical until EE available |
| NOT_APPLICABLE | Justgroup-specific / later phase |

## Forbidden

- Editing vendored modules as if they were product source
- Copying Enterprise trees, dumps, filestore, secrets, customer data
- Loading production Justgroup/Doralex data into this snapshot
