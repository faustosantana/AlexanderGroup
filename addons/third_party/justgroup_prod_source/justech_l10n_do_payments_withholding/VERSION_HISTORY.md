# Version History — justech_l10n_do_payments_withholding

## 19.0.1.6.11 — 2026-07-28 (Producción)

**UX — Configuración de retenciones**

- Ficha limpia: Empresa, Estado (badge), Cuenta (una línea), Naturaleza.
- Banners de advertencia; botones Configurar / Editar.
- Tabla por empresa resumida. Sin cambios de lógica contable.

Despliegue Producción: 2026-07-28 · backup `retention-config-ux-2026.1.6.11-20260728_130221`.

## 19.0.1.6.10 — 2026-07-28 (Producción)

**Arquitectura contable de retenciones (Fases 1–3)**

- Catálogo global + company.config + `_get_withholding_account` fail-closed.
- Wizard/GL; prorrateo parcial; UAT excluido de sync producción.
- RET01/RET02 intactos; sin remediación histórica.

## 19.0.1.6.8 — 2026-07-28 (DEV)

**Fase 1 — Base contable de retenciones**

- Catálogo global materializado + configs por empresa (inicialmente inactivas).
- Resolución fail-closed por empresa.
- UI / asistente / chatter catálogo y aviso legado en pagos.

## 19.0.1.6.7 — 2026-07-28 (Producción)

**Mejora UX - Facturas relacionadas en Pagos**

- Navegación mejorada en la sección Facturas relacionadas.
- Apertura directa de factura, contacto y pago.
- Visualización de NCF/e-CF.
- Balance pendiente desde residual contable (`account.move.amount_residual`).
- Limpieza de información técnica (Detalle NCF, Estado fiscal, DGII incomplete).
- Mejora de usabilidad para Contabilidad y Tesorería.
- Modal «Detalle por factura» con columnas operativas.

Despliegue Producción: 2026-07-28 · backup `payment-related-ux-20260728_003203`.

## 19.0.1.6.4 — 2026-07-20

HOTFIX 2026.1.4 — bloqueo de montos ≤ 0.

## 19.0.1.6.2 — 2026-07-15

ACL operativa para líneas de aplicación.
