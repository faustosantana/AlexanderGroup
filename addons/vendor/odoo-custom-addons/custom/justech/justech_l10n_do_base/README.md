# Módulo Fiscal RD — Justech ERP

Estándar corporativo de localización fiscal para República Dominicana.

## Arquitectura (Fase 3A)

Capa común de servicios fiscales:

| Directorio | Rol |
|------------|-----|
| `validators/` | RNC, NCF, contexto fiscal (Python puro) |
| `services/` | AbstractModels Odoo |
| `providers/` | Tipos documentales, config |
| `adapters/` | Integraciones externas (futuro) |

Documentación: `ARCHITECTURE.md`, `CHANGELOG.md`, `MIGRATION.md`, `ROADMAP.md`, `diagrams/`.

Validación anti-hardcode: `python3 tools/fiscal_no_hardcode_check.py`

## Comprobantes NCF (serie B)

| Prefijo | Uso |
|---------|-----|
| B01 | Factura de Crédito Fiscal |
| B02 | Factura de Consumo |
| B03 | Nota de Débito |
| B04 | Nota de Crédito |
| B11 | Comprobante de Compras |
| B12 | Registro Único de Ingresos |
| B13 | Gastos Menores |
| B14 | Regímenes Especiales |
| B15 | Gubernamental |
| B16 | Exportaciones |
| B17 | Pagos al Exterior |

## Módulos

- `justech_l10n_do_base` — tipos documentales, RNC, diarios
- `justech_l10n_do_ncf` — rangos, asignación, anulación, PDF
- `justech_l10n_do_reports` — DGII 606/607/608/609/623

## Certificación

```bash
odoo shell -d DB --no-http < scripts/fiscal-rd-final-certify-test.py
```

Evidencia: `evidence/fiscal-rd-final-certification/`

## eNCF (serie E)

Pendiente de módulo EDI/e-CF separado (E31–E47). Los exportadores 607/609 reconocen prefijos E en mapeos.
