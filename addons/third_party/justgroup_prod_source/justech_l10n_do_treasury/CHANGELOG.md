# Changelog — justech_l10n_do_treasury

## 19.0.1.6.3 — 2026-07-15

### Fixed
- Visibilidad operativa de menús Pagos / Clientes→Pagos / Proveedores→Pagos:
  además de `account.group_account_readonly`, incluyen
  `account.group_account_invoice` (Facturación / cobros / pagos).
- Sin menús nuevos, sin activar menús obsoletos «Registrar … / Aplicar».

## 19.0.1.6.0 — 2026-07-13

### Added
- Menú Contabilidad → Pagos: clientes / proveedores / todos (dominios reales `partner_type`).
- UX: diferenciar aplicación a factura vs conciliación bancaria; botón a extracto cuando CxC ya conciliada.

### Fixed
- Acción de conciliación ya no reabre líneas CxC/CxP conciliadas (caso PBNK1/outstanding).

## 19.0.1.5.0 — 2026-07-10

### Fixed
- Vista primaria de Pagos abiertos (lista/formulario) sin deformación del form Enterprise.
- Estados contable y bancario separados, etiquetas en español.

## 19.0.1.4.1 — 2026-07-10

### Fixed
- `treasury_bank_state`: considera la cuenta outstanding al evaluar conciliación bancaria.
