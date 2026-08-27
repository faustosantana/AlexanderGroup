# -*- coding: utf-8 -*-
"""Registry UX → grupos reales de Odoo (sin inventar seguridad paralela).

Cada sección:
- levels: escalera mutua (Selection) → xmlids reales
- caps: capacidades booleanas → xmlids reales y segregables
- module_xmlids: módulos Odoo que deben estar instalados para mostrar la sección
"""

# Riesgo: lectura | operativo | aprobacion | administracion | critico

JX_MODULES = (
    {
        "key": "sales",
        "label": "Ventas",
        "modules": ("sale",),
        "levels": (
            {
                "code": "none",
                "label": "Sin acceso",
                "xmlids": (),
                "can": (),
                "cannot": ("operar cotizaciones ni pedidos de venta",),
                "risk": "lectura",
            },
            {
                "code": "own",
                "label": "Usuario: solo sus documentos",
                "xmlids": ("sales_team.group_sale_salesman",),
                "can": (
                    "crear y gestionar sus propias cotizaciones/pedidos",
                    "confirmar sus pedidos (según flujo estándar)",
                ),
                "cannot": (
                    "ver documentos de otros vendedores",
                    "administrar equipos ni configuración de Ventas",
                ),
                "risk": "operativo",
            },
            {
                "code": "all",
                "label": "Usuario: todos los documentos",
                "xmlids": ("sales_team.group_sale_salesman_all_leads",),
                "can": (
                    "ver y operar cotizaciones/pedidos de todos los vendedores",
                ),
                "cannot": ("administrar configuración de Ventas",),
                "risk": "operativo",
            },
            {
                "code": "manager",
                "label": "Administrador",
                "xmlids": ("sales_team.group_sale_manager",),
                "can": (
                    "administrar Ventas (equipos, reportes, configuración autorizada)",
                    "operar todos los documentos comerciales",
                ),
                "cannot": ("administrar usuarios del sistema",),
                "risk": "administracion",
            },
        ),
        "caps": (
            {
                "code": "so_discount",
                "label": "Aplicar descuentos en líneas",
                "xmlids": ("sale.group_discount_per_so_line",),
                "can": ("aplicar descuento porcentual por línea de venta",),
                "cannot": ("aprobar políticas de descuento ajenas al grupo",),
                "risk": "aprobacion",
                "help": "Grupo estándar sale.group_discount_per_so_line.",
            },
            {
                "code": "so_credit_note",
                "label": "Emitir notas de crédito fiscales",
                "xmlids": ("l10n_do_accounting.group_l10n_do_fiscal_credit_note",),
                "can": ("crear notas de crédito fiscales (l10n_do)",),
                "cannot": ("anular NCF ni administrar rangos",),
                "risk": "aprobacion",
                "modules": ("l10n_do_accounting",),
                "help": "Grupo l10n_do_accounting.group_l10n_do_fiscal_credit_note.",
            },
            {
                "code": "so_cancel_fiscal",
                "label": "Cancelar facturas fiscales",
                "xmlids": ("l10n_do_accounting.group_l10n_do_fiscal_invoice_cancel",),
                "can": ("cancelar facturas fiscales cuando el flujo l10n_do lo permite",),
                "cannot": ("garantizar anulación NCF sin grupo fiscal correspondiente",),
                "risk": "critico",
                "modules": ("l10n_do_accounting",),
                "help": "Grupo l10n_do_accounting.group_l10n_do_fiscal_invoice_cancel.",
            },
        ),
    },
    {
        "key": "purchase",
        "label": "Compras",
        "modules": ("purchase",),
        "levels": (
            {
                "code": "none",
                "label": "Sin acceso",
                "xmlids": (),
                "can": (),
                "cannot": ("operar solicitudes ni órdenes de compra",),
                "risk": "lectura",
            },
            {
                "code": "user",
                "label": "Usuario",
                "xmlids": ("purchase.group_purchase_user",),
                "can": (
                    "crear solicitudes y órdenes de compra",
                    "seguir el flujo de aprobación estándar de su nivel",
                ),
                "cannot": ("administrar configuración de Compras",),
                "risk": "operativo",
            },
            {
                "code": "manager",
                "label": "Administrador",
                "xmlids": ("purchase.group_purchase_manager",),
                "can": (
                    "aprobar y administrar compras",
                    "configurar parámetros de Compras autorizados",
                ),
                "cannot": ("administrar usuarios del sistema",),
                "risk": "administracion",
            },
        ),
        "caps": (),
        "notes": (
            "Documentos recibidos / B11-B13-B17 no tienen grupos propios de Compras; "
            "dependen de Contabilidad + roles Fiscal (sección dinámica)."
        ),
    },
    {
        "key": "inventory",
        "label": "Inventario",
        "modules": ("stock",),
        "levels": (
            {
                "code": "none",
                "label": "Sin acceso",
                "xmlids": (),
                "can": (),
                "cannot": ("operar transferencias ni ajustes",),
                "risk": "lectura",
            },
            {
                "code": "user",
                "label": "Usuario",
                "xmlids": ("stock.group_stock_user",),
                "can": (
                    "registrar entradas/salidas y transferencias",
                    "participar en conteos según flujos estándar",
                ),
                "cannot": ("administrar valoración ni configuración de almacenes",),
                "risk": "operativo",
            },
            {
                "code": "manager",
                "label": "Administrador",
                "xmlids": ("stock.group_stock_manager",),
                "can": (
                    "administrar inventario, ubicaciones y valoración autorizada",
                    "validar operaciones de inventario",
                ),
                "cannot": ("administrar usuarios del sistema",),
                "risk": "administracion",
            },
        ),
        "caps": (
            {
                "code": "stk_lots",
                "label": "Registrar seriales / lotes",
                "xmlids": ("stock.group_production_lot",),
                "can": ("usar seguimiento por lote/número de serie",),
                "cannot": ("cambiar valoración contable por sí solo",),
                "risk": "operativo",
                "help": "Grupo stock.group_production_lot.",
            },
        ),
    },
    {
        "key": "accounting",
        "label": "Contabilidad",
        "modules": ("account",),
        # Incluidos en el ladder gestionado aunque no sean opciones de UI
        "ladder_extra_xmlids": (
            "account.group_account_readonly",
            "account.group_account_basic",
        ),
        "levels": (
            {
                "code": "none",
                "label": "Sin acceso",
                "xmlids": (),
                "can": (),
                "cannot": ("facturar, contabilizar ni administrar diarios",),
                "risk": "lectura",
            },
            {
                "code": "invoice",
                "label": "Facturación",
                "xmlids": ("account.group_account_invoice",),
                "can": (
                    "crear y publicar facturas/notas",
                    "registrar y aplicar pagos sobre documentos abiertos "
                    "(Odoo concede cobros, pagos y aplicación con el mismo grupo)",
                ),
                "cannot": (
                    "funciones completas de contabilidad (asientos avanzados)",
                    "administrar plan de cuentas / Impuestos / diarios como Administrador",
                ),
                "risk": "operativo",
                "warning": (
                    "Incluye cobros, pagos a proveedores y aplicar pagos a facturas "
                    "(un solo acceso en Odoo)."
                ),
            },
            {
                "code": "accountant",
                "label": "Contabilidad",
                "xmlids": ("account.group_account_user",),
                "can": (
                    "usar características completas de contabilidad",
                    "operar asientos y reportes contables estándar",
                ),
                "cannot": ("administrar configuración contable completa",),
                "risk": "aprobacion",
            },
            {
                "code": "manager",
                "label": "Administrador",
                "xmlids": ("account.group_account_manager",),
                "can": (
                    "administrar Contabilidad (diarios, impuestos, configuración)",
                    "gestionar catálogo de retenciones (implicación hacia Administrador de Retenciones)",
                ),
                "cannot": ("administrar usuarios del sistema por sí solo",),
                "risk": "critico",
                "warning": (
                    "Alto riesgo. Implica Facturación/Contabilidad y, en esta BD, "
                    "el catálogo de retenciones Justech."
                ),
            },
        ),
        "caps": (
            {
                "code": "accounting_recovery",
                "label": "Recuperación Contable",
                "xmlids": (
                    "justech_accounting_recovery.group_accounting_recovery",
                ),
                "modules": ("justech_accounting_recovery",),
                "can": (
                    "restablecer a borrador, cancelar, revertir y eliminar "
                    "asientos/pagos (segregación de funciones)",
                ),
                "cannot": (
                    "usar recuperación contable sin necesidad operativa autorizada",
                ),
                "risk": "critico",
                "warning": (
                    "Crítico / SoD. No sustituye Administrador Contable; "
                    "conceder solo a personal autorizado para recuperación."
                ),
                "help": (
                    "Grupo justech_accounting_recovery.group_accounting_recovery."
                ),
            },
        ),
        "notes": (
            "Las capacidades fiscales DGII/NCF se administran en «Fiscal República Dominicana». "
            "Pagos/Bancos detalla lo que Facturación realmente concede."
        ),
    },
    {
        "key": "fiscal",
        "label": "Fiscal República Dominicana",
        "modules": ("justech_l10n_do_base",),
        "levels": (
            {
                "code": "none",
                "label": "Sin acceso fiscal",
                "xmlids": (),
                "can": (),
                "cannot": ("operar funciones fiscales Justech",),
                "risk": "lectura",
            },
            {
                "code": "user",
                "label": "Usuario Fiscal",
                "xmlids": ("justech_l10n_do_base.group_justech_do_fiscal_user",),
                "can": (
                    "consultar información fiscal cotidiana",
                    "seleccionar tipos de comprobante en documentos",
                    "operar flujos fiscales de usuario (implica Facturación)",
                ),
                "cannot": (
                    "administrar rangos NCF",
                    "administrar configuración fiscal avanzada",
                ),
                "risk": "operativo",
                "warning": "Implica account.group_account_invoice (Facturación).",
            },
            {
                "code": "officer",
                "label": "Responsable Fiscal",
                "xmlids": ("justech_l10n_do_base.group_justech_do_fiscal_manager",),
                "can": (
                    "anular NCF según flujo Justech",
                    "gestionar operaciones fiscales avanzadas de responsable",
                    "generar/consultar reportes DGII autorizados a Responsable",
                ),
                "cannot": ("administrar configuración global de Fiscal Admin",),
                "risk": "aprobacion",
            },
            {
                "code": "admin_reader",
                "label": "Fiscal Admin / Lectura",
                "xmlids": ("justech_fiscal_admin.group_justech_fiscal_admin_user",),
                "can": (
                    "lectura ampliada de administración fiscal Justech",
                ),
                "cannot": (
                    "escribir configuración fiscal crítica (requiere Administrador Fiscal)",
                ),
                "risk": "operativo",
                "modules": ("justech_fiscal_admin",),
            },
            {
                "code": "admin",
                "label": "Administrador Fiscal",
                "xmlids": ("justech_fiscal_admin.group_justech_fiscal_admin_manager",),
                "can": (
                    "administrar rangos, tipos y configuración fiscal Justech",
                    "resolver incidencias fiscales",
                    "acceso de administración fiscal (alto privilegio)",
                ),
                "cannot": (
                    "administrar usuarios Odoo (base.group_system) por sí solo",
                    "obtener Inventario/Compras salvo otras asignaciones",
                ),
                "risk": "critico",
                "modules": ("justech_fiscal_admin",),
                "warning": (
                    "Crítico. Puede implicar e-CF Admin vía bridge Justech; "
                    "no concede Administración de Usuarios."
                ),
            },
        ),
        "caps": (),
    },
    {
        "key": "payments",
        "label": "Pagos y Bancos",
        "modules": ("account",),
        "levels": (),
        "caps": (
            {
                "code": "pay_invoice_access",
                "label": "Facturación / cobros / pagos / aplicar",
                "xmlids": ("account.group_account_invoice",),
                "can": (
                    "ver/registrar facturas",
                    "registrar cobros de clientes",
                    "registrar pagos a proveedores",
                    "aplicar pagos a facturas abiertas",
                ),
                "cannot": (
                    "una segregación independiente cobro vs pago vs aplicar "
                    "(no existe grupo separado en esta instancia)",
                    "administrar diarios como Administrador Contable",
                ),
                "risk": "operativo",
                "warning": (
                    "Es el mismo acceso que «Facturación» en Contabilidad "
                    "(cobros, pagos y aplicación)."
                ),
            },
            {
                "code": "pay_bank_validate",
                "label": "Validar / administrar cuentas bancarias",
                "xmlids": ("account.group_validate_bank_account",),
                "can": ("validar cuentas bancarias",),
                "cannot": ("reemplazar al Administrador Contable",),
                "risk": "administracion",
            },
        ),
        "notes": (
            "Si al operar pagos aparece un error de acceso fiscal, "
            "asigne también «Usuario Fiscal». No use Administrador Fiscal "
            "salvo que deba configurar el motor."
        ),
    },
    {
        "key": "withholding",
        "label": "Retenciones",
        "modules": ("justech_l10n_do_payments_withholding",),
        "levels": (
            {
                "code": "none",
                "label": "Sin administración de catálogo",
                "xmlids": (),
                "can": (),
                "cannot": ("administrar el catálogo Justech de retenciones",),
                "risk": "lectura",
            },
            {
                "code": "catalog_admin",
                "label": "Administrador de Retenciones",
                "xmlids": (
                    "justech_l10n_do_payments_withholding.group_justech_withholding_catalog_admin",
                ),
                "can": (
                    "administrar catálogo de retenciones Justech",
                ),
                "cannot": (
                    "sustituir el flujo operativo de aplicación en pagos "
                    "(ese flujo usa grupos Contabilidad/Facturación)",
                ),
                "risk": "administracion",
                "warning": (
                    "Puede estar implícito por Contabilidad / Administrador. "
                    "Quitar solo este nivel no elimina account.group_account_manager."
                ),
            },
        ),
        "caps": (),
        "notes": (
            "Registrar/aplicar retenciones en pagos: requiere Facturación/Contabilidad; "
            "no hay grupo «Usuario Retenciones» separado."
        ),
    },
    {
        "key": "ecf",
        "label": "e-CF",
        "modules": ("justech_ecf_core",),
        "levels": (
            {
                "code": "none",
                "label": "Sin acceso",
                "xmlids": (),
                "can": (),
                "cannot": ("acceder a operaciones e-CF",),
                "risk": "lectura",
            },
            {
                "code": "readonly",
                "label": "Solo lectura e-CF",
                "xmlids": ("justech_ecf_core.group_ecf_readonly",),
                "can": ("consultar documentos/eventos e-CF en lectura",),
                "cannot": ("enviar ni administrar e-CF",),
                "risk": "lectura",
            },
            {
                "code": "operator",
                "label": "Operador e-CF",
                "xmlids": ("justech_ecf_core.group_ecf_operator",),
                "can": ("operar envíos e-CF cotidianos",),
                "cannot": ("administrar configuración e-CF",),
                "risk": "operativo",
            },
            {
                "code": "responsible",
                "label": "Responsable e-CF",
                "xmlids": ("justech_ecf_core.group_ecf_responsible",),
                "can": ("supervisar operaciones e-CF",),
                "cannot": ("administración completa e-CF",),
                "risk": "aprobacion",
            },
            {
                "code": "admin",
                "label": "Administrador e-CF",
                "xmlids": ("justech_ecf_core.group_ecf_admin",),
                "can": ("administrar configuración e-CF",),
                "cannot": ("administrar usuarios Odoo por sí solo",),
                "risk": "critico",
            },
        ),
        "caps": (
            {
                "code": "ecf_auditor",
                "label": "Auditor e-CF",
                "xmlids": ("justech_ecf_core.group_ecf_auditor",),
                "can": ("auditar historial/eventos e-CF",),
                "cannot": ("administrar configuración e-CF",),
                "risk": "lectura",
            },
        ),
    },
    {
        "key": "warranty",
        "label": "Garantías",
        "modules": ("justech_warranty",),
        "levels": (
            {
                "code": "none",
                "label": "Sin acceso",
                "xmlids": (),
                "can": (),
                "cannot": ("usar el módulo de garantías",),
                "risk": "lectura",
            },
            {
                "code": "user",
                "label": "Usuario de Garantías",
                "xmlids": ("justech_warranty.group_warranty_user",),
                "can": ("ver, crear y procesar garantías según ACL del grupo",),
                "cannot": ("administrar configuración completa de garantías",),
                "risk": "operativo",
            },
            {
                "code": "manager",
                "label": "Administrador de Garantías",
                "xmlids": ("justech_warranty.group_warranty_manager",),
                "can": ("administrar garantías (incluye eliminación según ACL)",),
                "cannot": ("administrar usuarios Odoo por sí solo",),
                "risk": "administracion",
            },
        ),
        "caps": (),
    },
    {
        "key": "margins",
        "label": "Costos y Márgenes",
        "modules": ("justech_purchase_sale_margin_control",),
        "caps_title": "Acceso a secciones",
        # Ladder + technical + section caps cleared on Sin acceso / level change
        "ladder_extra_xmlids": (
            "justech_purchase_sale_margin_control.group_margin_auditor",
            "justech_purchase_sale_margin_control.group_margin_sales",
            "justech_purchase_sale_margin_control.group_margin_purchase",
            "justech_purchase_sale_margin_control.group_margin_finance",
            "justech_purchase_sale_margin_control.group_margin_sec_board",
            "justech_purchase_sale_margin_control.group_margin_sec_inbox",
            "justech_purchase_sale_margin_control.group_margin_sec_ops_view",
            "justech_purchase_sale_margin_control.group_margin_sec_ops_manage",
            "justech_purchase_sale_margin_control.group_margin_sec_margins_view",
            "justech_purchase_sale_margin_control.group_margin_sec_margins_manage",
            "justech_purchase_sale_margin_control.group_margin_sec_cxp_view",
            "justech_purchase_sale_margin_control.group_margin_sec_cxp_manage",
            "justech_purchase_sale_margin_control.group_margin_sec_reports_view",
            "justech_purchase_sale_margin_control.group_margin_sec_reports_export",
            "justech_purchase_sale_margin_control.group_margin_sec_config",
        ),
        "levels": (
            {
                "code": "none",
                "label": "Sin acceso",
                "xmlids": (),
                "default_caps": (),
                "can": (),
                "cannot": (
                    "ver el menú Costos y Márgenes",
                    "consultar costos, márgenes ni operaciones MTX",
                    "usar herramientas ni configuración del módulo",
                ),
                "risk": "lectura",
            },
            {
                "code": "user",
                "label": "Usuario",
                "xmlids": (
                    "justech_purchase_sale_margin_control.group_margin_readonly",
                ),
                "default_caps": ("m_inbox", "m_ops_view"),
                "can": (
                    "entrar al módulo Costos y Márgenes",
                    "ver Pendientes y Operaciones (lectura) según caps",
                ),
                "cannot": (
                    "ver Resumen financiero / CxP / Márgenes / Reportes por defecto",
                    "gestionar operaciones ni configuración",
                ),
                "risk": "lectura",
            },
            {
                "code": "responsable",
                "label": "Responsable",
                "xmlids": (
                    "justech_purchase_sale_margin_control.group_margin_finance",
                ),
                "default_caps": (
                    "m_inbox",
                    "m_ops_view",
                    "m_ops_manage",
                    "m_margins_view",
                    "m_margins_manage",
                    "m_reports_view",
                ),
                "can": (
                    "operar pendientes / operaciones / márgenes",
                    "usar herramientas funcionales",
                    "consultar reportes (sin exportar ni CxP/board por defecto)",
                ),
                "cannot": (
                    "Resumen financiero completo por defecto",
                    "Cuentas por Pagar por defecto",
                    "Configuración del módulo",
                ),
                "risk": "operativo",
            },
            {
                "code": "admin",
                "label": "Administrador",
                "xmlids": (
                    "justech_purchase_sale_margin_control.group_margin_admin",
                ),
                "default_caps": (
                    "m_board",
                    "m_inbox",
                    "m_ops_view",
                    "m_ops_manage",
                    "m_margins_view",
                    "m_margins_manage",
                    "m_cxp_view",
                    "m_cxp_manage",
                    "m_reports_view",
                    "m_reports_export",
                    "m_config",
                ),
                "can": (
                    "acceso completo al módulo Costos y Márgenes",
                    "configuración y auditoría del módulo",
                ),
                "cannot": (
                    "convertirse en Administrador del Sistema / Contabilidad / Ventas / Compras",
                ),
                "risk": "administracion",
            },
        ),
        "caps": (
            {
                "code": "m_board",
                "label": "Resumen financiero",
                "xmlids": ("justech_purchase_sale_margin_control.group_margin_sec_board",),
                "can": ("ver dashboard KPI financiero del módulo",),
                "cannot": (),
                "risk": "critico",
            },
            {
                "code": "m_inbox",
                "label": "Pendientes",
                "xmlids": ("justech_purchase_sale_margin_control.group_margin_sec_inbox",),
                "can": ("ver bandeja de pendientes",),
                "cannot": (),
                "risk": "operativo",
            },
            {
                "code": "m_ops_view",
                "label": "Operaciones — Ver",
                "xmlids": ("justech_purchase_sale_margin_control.group_margin_sec_ops_view",),
                "can": ("listar/consultar operaciones comerciales",),
                "cannot": ("ver campos de margen/costo sin permiso Márgenes",),
                "risk": "lectura",
            },
            {
                "code": "m_ops_manage",
                "label": "Operaciones — Gestionar",
                "xmlids": ("justech_purchase_sale_margin_control.group_margin_sec_ops_manage",),
                "implies_caps": ("m_ops_view",),
                "can": ("crear/editar operaciones y usar herramientas",),
                "cannot": (),
                "risk": "operativo",
            },
            {
                "code": "m_margins_view",
                "label": "Márgenes — Ver",
                "xmlids": ("justech_purchase_sale_margin_control.group_margin_sec_margins_view",),
                "can": ("ver menú Márgenes y campos de costo/margen",),
                "cannot": (),
                "risk": "critico",
            },
            {
                "code": "m_margins_manage",
                "label": "Márgenes — Gestionar",
                "xmlids": ("justech_purchase_sale_margin_control.group_margin_sec_margins_manage",),
                "implies_caps": ("m_margins_view",),
                "can": ("gestionar datos de margen/costo en operaciones",),
                "cannot": (),
                "risk": "operativo",
            },
            {
                "code": "m_cxp_view",
                "label": "Cuentas por Pagar — Ver",
                "xmlids": ("justech_purchase_sale_margin_control.group_margin_sec_cxp_view",),
                "can": ("consultar auxiliar CxP del módulo",),
                "cannot": (),
                "risk": "critico",
            },
            {
                "code": "m_cxp_manage",
                "label": "Cuentas por Pagar — Gestionar",
                "xmlids": ("justech_purchase_sale_margin_control.group_margin_sec_cxp_manage",),
                "implies_caps": ("m_cxp_view",),
                "can": ("gestionar auxiliar CxP",),
                "cannot": (),
                "risk": "operativo",
            },
            {
                "code": "m_reports_view",
                "label": "Reportes — Ver",
                "xmlids": ("justech_purchase_sale_margin_control.group_margin_sec_reports_view",),
                "can": ("abrir reportes del módulo",),
                "cannot": (),
                "risk": "lectura",
            },
            {
                "code": "m_reports_export",
                "label": "Reportes — Exportar",
                "xmlids": ("justech_purchase_sale_margin_control.group_margin_sec_reports_export",),
                "implies_caps": ("m_reports_view",),
                "can": ("exportar reportes (p. ej. CxP XLSX)",),
                "cannot": (),
                "risk": "aprobacion",
            },
            {
                "code": "m_config",
                "label": "Configuración",
                "xmlids": ("justech_purchase_sale_margin_control.group_margin_sec_config",),
                "can": ("administrar configuración del módulo",),
                "cannot": (),
                "risk": "administracion",
            },
        ),
        "notes": (
            "Nivel = preset. Las casillas controlan menús, permisos y campos sensibles.",
            "Solo afecta Costos y Márgenes. No otorga administración de Ajustes, Contabilidad, Ventas ni Compras.",
        ),
    },
    {
        "key": "fees",
        "label": "Fees recurrentes",
        "modules": ("justech_recurring_fee",),
        "levels": (
            {
                "code": "none",
                "label": "Sin acceso",
                "xmlids": (),
                "can": (),
                "cannot": ("gestionar fees recurrentes",),
                "risk": "lectura",
            },
            {
                "code": "user",
                "label": "Usuario Fees",
                "xmlids": ("justech_recurring_fee.group_recurring_fee_user",),
                "can": ("operar fees recurrentes (implica Usuario Ventas propios)",),
                "cannot": ("administrar configuración de Fees",),
                "risk": "operativo",
                "warning": "Implica sales_team.group_sale_salesman.",
            },
            {
                "code": "manager",
                "label": "Responsable Fees",
                "xmlids": ("justech_recurring_fee.group_recurring_fee_manager",),
                "can": ("administrar fees recurrentes",),
                "cannot": ("administrar usuarios Odoo por sí solo",),
                "risk": "administracion",
            },
        ),
        "caps": (),
    },
    {
        "key": "crm",
        "label": "CRM",
        "modules": ("crm",),
        "levels": (
            {
                "code": "none",
                "label": "Sin flag de Leads",
                "xmlids": (),
                "can": (),
                "cannot": ("mostrar menú de Leads (flag CRM)",),
                "risk": "lectura",
            },
            {
                "code": "leads",
                "label": "Usar Leads",
                "xmlids": ("crm.group_use_lead",),
                "can": ("mostrar el menú de Leads",),
                "cannot": (
                    "sustituir la escalera de Ventas (el acceso CRM operativo "
                    "sigue dependiendo de grupos de Ventas)",
                ),
                "risk": "operativo",
                "warning": "En Odoo no existe escalera CRM User/Admin independiente de Ventas.",
            },
        ),
        "caps": (),
    },
    {
        "key": "hr",
        "label": "Recursos Humanos",
        "modules": ("hr",),
        "levels": (
            {
                "code": "none",
                "label": "Sin acceso",
                "xmlids": (),
                "can": (),
                "cannot": ("gestionar empleados",),
                "risk": "lectura",
            },
            {
                "code": "user",
                "label": "Encargado",
                "xmlids": ("hr.group_hr_user",),
                "can": ("gestionar empleados como Encargado",),
                "cannot": ("administrar configuración HR completa",),
                "risk": "operativo",
            },
            {
                "code": "manager",
                "label": "Administrador",
                "xmlids": ("hr.group_hr_manager",),
                "can": ("administrar Empleados/HR",),
                "cannot": ("administrar usuarios Odoo por sí solo",),
                "risk": "administracion",
            },
        ),
        "caps": (),
    },
    {
        "key": "admin",
        "label": "Administración Justech",
        "modules": ("justech_admin_center",),
        "levels": (
            {
                "code": "none",
                "label": "Sin acceso",
                "xmlids": (),
                "can": (),
                "cannot": ("usar consola Justech Admin Center",),
                "risk": "lectura",
            },
            {
                "code": "user",
                "label": "Usuario consola Justech",
                "xmlids": ("justech_admin_center.group_justech_admin_center_user",),
                "can": ("usar funciones de usuario del Admin Center",),
                "cannot": ("administrar el Admin Center",),
                "risk": "operativo",
            },
            {
                "code": "manager",
                "label": "Administrador Justech",
                "xmlids": ("justech_admin_center.group_justech_admin_center_manager",),
                "can": ("administrar Justech Admin Center",),
                "cannot": ("equivaler automáticamente a Administrador del Sistema Odoo",),
                "risk": "critico",
                "warning": "Puede implicar e-CF Admin vía bridge; verificar implied_ids.",
            },
        ),
        "caps": (),
    },
)
