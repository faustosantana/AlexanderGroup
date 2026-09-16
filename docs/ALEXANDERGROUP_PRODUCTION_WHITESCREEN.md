# ODOO WHITE SCREEN INCIDENT

Fecha: 2026-09-16.
Entorno: **PRODUCCIÓN** `doralexgroup.cloud`.
**PROD STATUS: FIXED.**

---

```
ODOO WHITE SCREEN INCIDENT

ROOT CAUSE:
  /odoo (sin sesión) redirige a /web/login envuelto por website.
  web.login pinta form.oe_login_form con d-none hasta que monte
  <owl-component name="web.user_switch">.
  Tras el -u del overlay, las interacciones OWL públicas no montaron
  el switcher. El form siguió oculto → centro de página en blanco
  (header/footer del website sí se veían).

AFFECTED COMPONENT:
  web.login + web.user_switch (frontend website).
  justech_alexander_ux 19.0.1.6.0 no creó el d-none (es core Odoo 19),
  pero el rebuild de assets/registry dejó el login dependiente de un
  mount OWL que no ocurrió. H17 navbar no era la causa del blanco
  anónimo.

HTTP:
  /odoo → 303 → /web/login 200
  /web 303 → /web/login 200
  /web/health 200 {"status":"pass"}
  /web/session/authenticate 200 (sesión interna)

WEB ASSETS:
  frontend CSS/JS 200 (tras hotfix hashes nuevos
  assets_frontend_minimal 56635c5, lazy 5db2bc6)
  web.assets_web.min.js 200 (10.5M)
  web.assets_web.min.css 200 (1.5M)
  debug=assets: form visible (sin d-none)

JS CONSOLE:
  sin traceback en logs Odoo. El síntoma era DOM: form d-none +
  owl-component vacío.

ODOO LOGS:
  sin ERROR/CRITICAL/ParseError post-hotfix 20:44Z.

FIX APPLIED:
  justech_alexander_ux 19.0.1.6.1
  - inherit web.login: t-attf-class="oe_login_form" (sin d-none)
  - JS mínimo en web.assets_frontend_minimal
  - navbar H17: sin xpath replace de brand (CSS ya oculta);
    click handler en una línea con home_menu opcional

MODULE UPDATED: justech_alexander_ux only (19.0.1.6.1)
ASSETS REBUILT: YES (frontend_minimal + frontend_lazy)
ODOO RESTARTED: YES (solo doralex-production-odoo)

BROWSER /ODOO: PASS (formulario correo/contraseña/Iniciar sesión visible)
NAVBAR: PASS (webclient body.o_web_client + assets_web 200)
APPS: PASS (load_menus: Sales, Contacts, Invoices, Quotations, …)
SALES: PASS (sale.menu_sale_quotations / sale.sale_order_menu)
ACCOUNTING: PASS (account invoices/bills menus)
MULTICOMPANY: PASS (sesión con compañías 8 y 11)

POST-FIX SMOKE:
  approval OFF 8–13
  padrón OFF
  ITBIS 16 SALE count=6
  login visible normal y ?debug=assets
  probe user desactivado

ERRORS REMAINING:
  web.user_switch sigue sin montar en login anónimo (ya no bloquea:
  el form es visible). No es fallo de acceso.

ROLLBACK REQUIRED: NO
ROLLBACK EXECUTED: NO

PROD STATUS: FIXED
```
