# Changelog — justech_admin_center

## 19.0.2.12.1 — 2026-08-20

- Inverses de roles espejo (e-CF / Garantías / Admin Justech / Finanzas / caps):
  no-op si el valor coincide con `group_ids`; siguen rechazando cambios reales
  por esa vía (usar pestaña Permisos).
- `create`: strip de campos espejo para que el formulario Nuevo no dispare el guard
  al reenviar `justech_*_role='none'`.

## 19.0.2.11.1 — 2026-07-12

- Reconstrucción UX de Administración Justech: dashboard nativo simplificado, taxonomía de estados única y pendientes solo accionables.
- Garantías / Fiscal / Estado del sistema sin HTML crudo; UAT fuera de la consola principal; navegación Empresa → Producto → Capacidad.

## 19.0.2.6.0 — 2026-07-12

- Cadena de roles: System → Administrador Justech → Administrador e-CF (implied_ids).
- AccessError e-CF corregido para System/Justech Admin; roles e-CF en ficha de usuario.
- Gate de reauth ya no lanza AccessError en `check_access` (evita salida al login).
- Jerarquía visual 1 / 1.1 / 1.3; pantallas de producto simplificadas; hub e-CF reorganizado.

## 19.0.2.5.0 — 2026-07-12

- Acciones MISS de Centro Fiscal / Salud Fiscal cableadas a operaciones reales.
- Hubs Padrón / Fiscal / Tesorería; e-CF integrado en Justech Fiscal.
- `has_operation_action` oculta «Abrir operación» cuando no hay destino útil.
- Diagnósticos reales por submódulo; UX en español; contraste claro/oscuro validado.

## 19.0.2.0.0 — 2026-07-11

- Consola Enterprise: productos → submódulos, dashboard responsive, contraste claro/oscuro.
- Activación / desactivación / motor fiscal por empresa con preview y auditoría.
- Reautenticación reforzada (hash env PBKDF2 o clave Justech), sesión 15 min, rate limit.
- Secretos solo por entorno (`JUSTECH_ADMIN_CENTER_PASSWORD_HASH`); nunca en Git.
- Catálogo dinámico enriquecido; instalación con lock advisory; sin desinstalación en v1.

## 19.0.1.0.1 — 2026-07-11

- Grupos Odoo 19 con `res.groups.privilege` (sin `category_id`).
- Settings app con componente `<setting>`.
- Dominios de usuarios con `group_ids` (Odoo 19).
- Gate de instalación: validar `justech_*` antes de buscar en addons.

## 19.0.1.0.0 — 2026-07-11

- Consola Settings → Administración Justech (KPI, catálogo kanban, diagnóstico, auditoría).
- Registro dinámico vía `justech_admin_center` en manifests.
- Instalación / activación / desactivación con preview, lock advisory y auditoría.
- Permisos Justech en ficha de usuario; matriz de roles funcionales.
- Integración soft con Fiscal, NCF, Reportes, Pagos, Tesorería, Auditoría y Garantías (discovery).
