# ODOO WHITE SCREEN INCIDENT

Fecha: 2026-09-16.
Entorno: **PRODUCCIÓN** `doralexgroup.cloud`.
**PROD STATUS: FIXED.**

Hubo dos capas:

1. Login anónimo (`/web/login`) oculto por `d-none` + `web.user_switch`
   sin montar — corregido en **19.0.1.6.1**.
2. Webclient autenticado (`/odoo`) en blanco porque OWL no compilaba
   `web_enterprise.EnterpriseNavBar` — corregido en **19.0.1.6.2**.

---

```
ODOO WHITE SCREEN INCIDENT

ROOT CAUSE:
  justech_alexander_ux 19.0.1.6.0/1.6.1 heredaba web_enterprise.EnterpriseNavBar
  y sobreescribía t-on-click.prevent con JS que OWL 19 no compile:
  optional chaining ?. y paréntesis extra
  (this.hm || this.env.services.home_menu)?.toggle(true)
  → Uncaught Error: Failed to compile template
    'web_enterprise.EnterpriseNavBar'. Unexpected token '('
  → Owl destruye el root component → pantalla blanca.
  El login 1.6.1 (form sin d-none) era correcto; el webclient seguía roto.

AFFECTED COMPONENT:
  justech_alexander_ux H17 navbar.xml (OWL inherit EnterpriseNavBar)
  Bundle compilado web.assets_web.min.js (hash viejo 3d6f3d9)

HTTP:
  /odoo → 303 → /web/login 200 (anónimo)
  /odoo autenticado 200 · body.o_web_client · session_info
  /web/login 200 · form.oe_login_form sin d-none
  /web/health 200 {"status":"pass"}
  /web/session/get_session_info 200 uid=18
  /web/webclient/load_menus 200 87k

WEB ASSETS:
  Tras rebuild: /web/assets/4d3d5ed/web.assets_web.min.js 200 JS 10.5M
  /web/assets/e6465b3/web.assets_web.min.css 200 CSS 1.5M
  debug=assets: web.assets_web.js 200 15.9M (no min)
  Template 1.6.2 en el bundle: solo title/aria-label Inicio
  Sin (this.hm || this.env.services.home_menu)
  Sin 404/500 de assets

JS CONSOLE:
  Sin Failed to compile template web_enterprise.EnterpriseNavBar
  Sin Unexpected token '('
  Sin Owl destroying root
  Warning residual (no bloquea): studio_hotfix TableUIPlugin

ODOO LOGS:
  Sin ERROR/CRITICAL/Traceback/ParseError/KeyError nuevos
  post -u 1.6.2 + restart + rebuild.

FIX APPLIED:
  justech_alexander_ux 19.0.1.6.2
  - navbar.xml: quitar override t-on-click (queda handler nativo)
  - conservar title/aria-label Inicio + CSS hide brand
  - login 1.6.1 intacto
  - DELETE solo ir.attachment /web/assets web.assets_web*
    y web.assets_backend* (regenerables)
  - restart doralex-production-odoo

MODULE UPDATED: justech_alexander_ux only (19.0.1.6.2)
ASSETS REBUILT: YES (web.assets_web 4d3d5ed + backend a23aec0)
ODOO RESTARTED: YES (solo doralex-production-odoo)

BROWSER /ODOO: PASS (apps grid + navbar, no blanco)
NAVBAR: PASS
APPS: PASS (19 apps, hamburguesa/Inicio nativo)
SALES: PASS (/odoo/sales Quotations)
ACCOUNTING: PASS (/odoo/customer-invoices con grupo RO temporal)
MULTICOMPANY: PASS (Doralex 11 ↔ Blue Elite 8)

POST-FIX SMOKE:
  approval OFF compañías 8–13
  padrón OFF · cron inactivo
  ITBIS 16 SALE ids 461–466
  DX catalog justech.do.withholding.catalog count=19
  Propet / Proforma / Quotation report actions presentes
  draft cancel helper presente
  frozen: payments 19.0.1.7.2 · multi pay 19.0.1.5.4
          margins 19.0.8.29.38 · trace 19.0.1.2.11
  probe user 18 desactivado de nuevo
  sin operaciones fiscales creadas

ERRORS REMAINING:
  studio_hotfix TableUIPlugin warning (preexistente, no bloquea)
  web.user_switch sigue sin montar en login anónimo
  (el form ya es visible sin d-none)

ROLLBACK REQUIRED: NO
ROLLBACK EXECUTED: NO

PROD STATUS: FIXED
```
