# Doralex — Decisión Enterprise (ENTERPRISE_DECISION = DONE)

> Justgroup = **Odoo 19 Enterprise** (`19.0+e-20260324`, verificado read-only).
> Doralex corre **Community** (`odoo:19`) y **no** dispone de licencia/fuente
> Enterprise legítima propia. Los addons Enterprise de Justgroup **no** se copian
> (licenciamiento por instancia). Arquitectura ya enterprise-ready
> (`addons_path = /mnt/enterprise,/mnt/custom-addons`; dir `enterprise` vacío).

## Decisión

`ENTERPRISE_STATUS = BLOCKED_BY_ENTERPRISE_SOURCE` para Doralex hasta que tenga su
**propia** suscripción. Se opera con **Community + módulos custom** (estos últimos,
cuando haya acceso de solo lectura a Justgroup). Al obtener licencia propia, se
instalan los módulos Enterprise **sin reconstruir** (solo colocar addons en
`/opt/doralex/enterprise` e `-i modulo`).

## ENTERPRISE_REQUIRED_FOR_DORALEX

| Módulo (Enterprise) | Función | Impacto si NO se instala |
| ------------------- | ------- | ------------------------ |
| `account_accountant` | Contabilidad completa: conciliación bancaria, activos, presupuestos, diferidos | Se opera con **Invoicing** (`account`, Community): facturación, diarios, impuestos, CxC/CxP básicos sí; conciliación automática y contabilidad avanzada no (parche parcial con OCA) |
| `account_reports` | Reportes financieros oficiales (Balance, PyG, libros) | Sin reportes financieros nativos; alternativa OCA `account_financial_report` (parcial) |
| `account_followup` | Seguimiento/recordatorios de CxC | Sin follow-ups automáticos; gestión manual |
| `l10n_do_edi` (e-CF RD) | Facturación electrónica e-CF (DGII) | Sin e-CF electrónico nativo; **NCF** básico cubrible con `l10n_do` Community + custom; e-CF requiere Enterprise o módulo custom/OCA |
| `web_studio` | Prototipado visual de vistas/campos | Personalización solo por **código versionado** (aceptable; ya es el estándar del proyecto) |
| `documents` | Gestión documental (DMS) | Sin DMS; usar adjuntos estándar (`ir.attachment`) |
| `sign` | Firma electrónica | Sin firma nativa |
| `helpdesk` | Mesa de ayuda / tickets | Sin Helpdesk; alternativa `project` o formularios web |
| `planning`, `timesheet_grid` (opc.) | Programación y partes de horas avanzados | Se cubre parcialmente con `project` Community |

## Qué SÍ cubre Community (ya instalado/validado en DEV)

Ventas (`sale_management`), Compras (`purchase`), Inventario (`stock`),
Invoicing/CxC/CxP básico (`account`), CRM (`crm`), Proyectos (`project`),
RRHH base (`hr`, `hr_holidays`), Multiempresa, Márgenes (`sale_margin`),
Localización RD base (`l10n_do`), Reportes **QWeb/PDF** personalizables.

## Funcionalidades que probablemente vendrán de custom Justech (pendiente de auditar)

`justech_l10n_do_payments_withholding` (retenciones RD), `multi_invoice_manual_payment_prod`,
`justech_purchase_sale_margin_control` (márgenes), `justech_sale_purchase_trace`
(trazabilidad). Requieren acceso al código de Justgroup para auditar/adaptar (no
son Enterprise; son custom). Ver `JUSTGROUP_MODULE_INVENTORY.md`.
