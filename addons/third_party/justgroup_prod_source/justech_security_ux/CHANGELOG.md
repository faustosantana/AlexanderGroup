# Changelog — justech_security_ux

## [19.0.4.1.9] — 2026-08-20 — User company access UX

### Added
- Pestaña **Empresas** (admin): Empresa principal (`company_id`) + Empresas
  permitidas (`company_ids` con checkboxes).
- Validación: la empresa principal debe estar entre las permitidas.
- Write de `company_id`/`company_ids` restringido a System / Admin Justech.

### Fixed
- `company_id` / `company_ids` vivían en `access_rights`, página ocultada por
  Security UX; ya no dependen de Developer Mode.

## [19.0.4.1.8] — 2026-08-20 — Coerce web_save color_scheme=false

### Fixed
- Usuarios → Nuevo posts related `color_scheme: false` on `res.users` via
  `web_save`; coerce to `system` on create/write (users + settings).

## [19.0.4.1.7] — 2026-08-20 — New-user Guardar color_scheme

### Fixed
- `res.users.settings` create defaults `color_scheme='system'` when missing,
  unblocking Usuarios → Nuevo → Guardar (Invitado path).

## [19.0.4.1.6] — 2026-08-20 — New-user creation 2.0 (permissions before save)

### Added
- CREATE MODE: catálogo visible sin `resId`; estado pendiente en `sessionStorage`.
- `jx_default_permission_state()` — defaults seguros (todo «Sin acceso»).
- `jx_apply_permission_state(state)` — aplica pending vía `jx_apply_level`/`jx_apply_cap`.
- Tras Guardar: aplica pending al nuevo `user_id` y refresca desde servidor.

### Fixed
- CREATE ya no depende del mensaje «Guarda el usuario…».
- Strip de campos espejo `justech_*_role` en `create` (evita pelear con Admin Center).

### Unchanged
- ACL / record rules / Margins granular — sin cambios.
- Guard Admin Center permanece; mutación solo por motor Security UX.

## [19.0.4.1.5] — 2026-08-20 — New-user Permisos no hang

### Fixed
- Nuevo usuario (formulario sin `resId` / URL `/users/new`): la pestaña Permisos
  ya no queda en «Cargando permisos…» indefinidamente.
- Sin uid: mensaje estable «Guarda el usuario para configurar sus permisos.»
- Tras guardar (URL `/users/<id>`): el editor carga automáticamente.
- Errores RPC dejan de mantener el spinner (mensaje de error explícito).

### Unchanged
- ACL / record rules / Margins granular 19.0.8.29.1 — sin cambios de seguridad.

## [19.0.4.1.1] — 2026-07-15 — Hotfix texto vertical en notas

### Fixed
- Renderer JS: `normalizeNotes` une listas de caracteres (catálogo `list(str)`)
  en un solo párrafo; deja de crear un nodo por letra.
- CSS: `overflow-wrap: break-word` (no `anywhere`) en notas/labels.

## [19.0.4.1.0] — 2026-07-15 — Pestaña única «Permisos»

### Changed
- Una sola pestaña de usuario: «Permisos» (antes Permisos Justech).
- Matriz nativa `access_rights` oculta de la ficha (Grupos vía menú técnico).
- UI sin «Ver implementación técnica», sin resumen Puede/No puede, sin banner.

### Unchanged
- Escritura quirúrgica (4)/(3) en `group_ids`. Sin ACL/rules/implied nuevos.

## [19.0.4.0.0] — 2026-07-15 — Rearquitectura: group_ids única fuente

### Removed
- Campos `jx_lvl_*` / `jx_cap_*` y todo compute/inverse de sincronización.
- Helpers `_jx_sync_level` / `_jx_sync_cap` / proyección paralela.

### Added
- API `jx_catalog` / `jx_permission_state` / `jx_summary` / `jx_apply_level` / `jx_apply_cap`.
- UI JS que escribe (4)/(3) directo en `group_ids`.
- Nivel fiscal «Fiscal Admin / Lectura».

### Unchanged
- ACL / Record Rules / implied_ids: 0 cambios estructurales.
- Sin tablas auxiliares. Sin Hellenia.
