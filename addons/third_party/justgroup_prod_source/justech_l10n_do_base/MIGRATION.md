# Migración — justech_l10n_do_base

## 19.0.1.5.0 → 19.0.1.6.0 (Fase 3A Sprint 1)

### Impacto

**Ningún cambio de datos ni de UX.** Refactor arquitectónico interno.

### Procedimiento (erp.justech.do / lab)

```bash
# 1. Backup BD lab (obligatorio)
# 2. Actualizar código rama feature/fiscal-standard-phase3a
# 3. Upgrade módulo
odoo -u justech_l10n_do_base -d justech_lab --stop-after-init
# 4. Ejecutar tests
odoo -d justech_lab --test-enable --stop-after-init \
  -i justech_l10n_do_base --test-tags=justech_fiscal_validators
```

### Rollback

```bash
odoo -u justech_l10n_do_base -d justech_lab --stop-after-init
# Restaurar código commit anterior + BD backup si necesario
```

### Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Servicios no cargados | `-u justech_l10n_do_base` regenera registry |
| Validación RNC distinta | Tests + mismos regex en `validators/rnc_format.py` |

### Producción

**No aplicar** hasta validación completa en lab y aprobación explícita.
