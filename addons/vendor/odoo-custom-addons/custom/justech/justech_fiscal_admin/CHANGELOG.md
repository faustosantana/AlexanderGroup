# Changelog

## 19.0.1.10.0

- RC-002: disable `ncf_dual_write` (emitted NCF SoT = Justech)
- Fiscal role inverse on res.users
- Open NCF ranges via fiscal range center

— justech_fiscal_admin

## 19.0.1.8.5 — 2026-07-14

- Centro Fiscal: pestaña Compras (recibidos, emitidos, costos/gastos, rangos, incidencias).
- ACL escritura sobre `justech.do.dgii.expense.type` para Administrador Fiscal.

## 19.0.1.8.0 — 2026-07-11

- Gate Final de Producción v1.0: certificación PASS (Gates 1–5) en `justech_dev`.
- Documentación go-live en `evidence/gate-final-produccion-v1/`.
- Sin cambios funcionales de producto; marca de release certificada.

## 19.0.1.7.0 — 2026-07-11

- Centro Fiscal: botón «Reimportar tras restore» para padrón global vacío.
- Reintento de última importación usa adjunto fallido cuando existe.
- Integración Enterprise padrón DGII (lock, cron, historial/checksum).

## 19.0.1.6.0 — 2026-07-11

- Resolución de empresa del Centro Fiscal vía `env.company` / `allowed_company_ids` (no fija JUSTECH).
- Roles: Responsable (solo lectura + revalidar), Usuario (operativo limitado), Contador/Ventas/Compras sin menú / sin AccessError.
- Health check: elimina falsos positivos de padrón `running` huérfano; estado global verde con 781,980 RNCs.
- ACL y menús alineados a grupos fiscal officer / user / admin.

## 19.0.1.5.0 — 2026-07-11

- Roles fiscales: Usuario / Responsable / Administrador Fiscal (SoD vs Contable).
- Singleton Centro Fiscal multiempresa (4/4) sin AccessError al cambiar empresa.
- Salud Fiscal con detalle estructurado (severidad, impacto, acción).
- Permisos fiscales en Usuarios + sección Usuarios y permisos en Centro Fiscal.
- Feature Flags y padrón DGII administrables por Administrador Fiscal / Settings.

## 19.0.1.2.1 — 2026-07-10

- Estabilización Centro de Administración Fiscal (sin RPC_ERROR en erp.justech.do).
