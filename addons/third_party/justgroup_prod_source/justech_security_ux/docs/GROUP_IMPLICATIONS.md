# GROUP_IMPLICATIONS — justech_dev

Cada grupo → grupos que implica · quien lo implica.

## `account.group_account_basic`

- **Nombre:** Contabilidad / Básico
- **Implica:** `account.group_account_invoice`, `account.group_account_readonly`
- **Implícito por:** `account.group_account_manager`, `account.group_account_user`

## `account.group_account_invoice`

- **Nombre:** Contabilidad / Facturación
- **Implica:** `base.group_user`
- **Implícito por:** `account.group_account_basic`, `justech_l10n_do_base.group_justech_do_fiscal_user`, `l10n_do_accounting.group_l10n_do_debit_note`, `l10n_do_accounting.group_l10n_do_fiscal_credit_note`, `l10n_do_accounting.group_l10n_do_fiscal_invoice_cancel`

## `account.group_account_manager`

- **Nombre:** Contabilidad / Administrador
- **Implica:** `account.group_account_basic`, `account.group_account_user`, `justech_l10n_do_payments_withholding.group_justech_withholding_catalog_admin`
- **Implícito por:** —

## `account.group_account_readonly`

- **Nombre:** Contabilidad / Mostrar funciones de contabilidad: solo lectura
- **Implica:** `base.group_user`
- **Implícito por:** `account.group_account_basic`, `account.group_account_user`

## `account.group_account_user`

- **Nombre:** Contabilidad / Mostrar características de contabilidad completas
- **Implica:** `account.group_account_basic`, `account.group_account_readonly`
- **Implícito por:** `account.group_account_manager`

## `account.group_delivery_invoice_address`

- **Nombre:** Dirección de entrega
- **Implica:** —
- **Implícito por:** `base.group_user`

## `account.group_validate_bank_account`

- **Nombre:** Banco / Validar cuenta bancaria
- **Implica:** —
- **Implícito por:** `base.group_system`

## `api_doc.group_allow_doc`

- **Nombre:** Documentación técnica
- **Implica:** —
- **Implícito por:** `base.group_system`

## `approvals.group_approval_manager`

- **Nombre:** Aprobaciones / Administrador
- **Implica:** `approvals.group_approval_user`
- **Implícito por:** —

## `approvals.group_approval_user`

- **Nombre:** Aprobaciones / Encargado: Aprobar todas las solicitudes
- **Implica:** `base.group_user`
- **Implícito por:** `approvals.group_approval_manager`

## `base.default_user_group`

- **Nombre:** Acceso predeterminado para usuarios nuevos
- **Implica:** `helpdesk.group_helpdesk_manager`
- **Implícito por:** —

## `base.group_allow_export`

- **Nombre:** Exportar / Permitido
- **Implica:** —
- **Implícito por:** `base.group_system`

## `base.group_erp_manager`

- **Nombre:** Permisos de acceso
- **Implica:** `base.group_user`, `justech_global_audit_log.group_justech_audit_manager`, `justech_warranty.group_warranty_manager`
- **Implícito por:** `base.group_system`

## `base.group_multi_currency`

- **Nombre:** Multimonedas
- **Implica:** —
- **Implícito por:** `base.group_user`

## `base.group_no_one`

- **Nombre:** Características técnicas
- **Implica:** —
- **Implícito por:** `base.group_system`, `base.group_user`

## `base.group_partner_manager`

- **Nombre:** Contacto / Creación
- **Implica:** —
- **Implícito por:** `base.group_system`

## `base.group_portal`

- **Nombre:** Rol / Portal
- **Implica:** `stock.group_lot_on_delivery_slip`, `stock.group_production_lot`, `website.group_multi_website`, `website.website_page_controller_expose`
- **Implícito por:** —

## `base.group_public`

- **Nombre:** Rol / Público
- **Implica:** `website.group_multi_website`, `website.website_page_controller_expose`
- **Implícito por:** —

## `base.group_sanitize_override`

- **Nombre:** Evitar la depuración de campos HTML
- **Implica:** —
- **Implícito por:** `base.group_system`, `website.group_website_designer`

## `base.group_system`

- **Nombre:** Rol / Administrador
- **Implica:** `account.group_validate_bank_account`, `api_doc.group_allow_doc`, `base.group_allow_export`, `base.group_erp_manager`, `base.group_no_one`, `base.group_partner_manager`, `base.group_sanitize_override`, `justech_admin_center.group_justech_admin_center_manager`, `justech_fiscal_admin.group_justech_fiscal_admin_manager`, `justech_global_audit_log.group_justech_audit_manager`, `justech_recurring_fee.group_recurring_fee_manager`, `justech_warranty.group_warranty_manager`, `mail.group_mail_canned_response_admin`, `mail.group_mail_template_editor`, `product.group_product_manager`, `website.group_website_designer`
- **Implícito por:** —

## `base.group_user`

- **Nombre:** Rol / Usuario
- **Implica:** `account.group_delivery_invoice_address`, `base.group_multi_currency`, `base.group_no_one`, `hr_payroll.group_payslip_display`, `product.group_product_pricelist`, `product.group_product_variant`, `project.group_project_stages`, `purchase.group_send_reminder`, `sale.group_discount_per_so_line`, `sale.group_proforma_sales`, `sale_management.group_sale_order_template`, `stock.group_lot_on_delivery_slip`, `stock.group_production_lot`, `stock.group_stock_multi_locations`, `stock_account.group_lot_on_invoice`, `uom.group_uom`, `website.group_multi_website`
- **Implícito por:** `account.group_account_invoice`, `account.group_account_readonly`, `approvals.group_approval_user`, `base.group_erp_manager`, `documents.group_documents_user`, `event.group_event_registration_desk`, `helpdesk.group_helpdesk_user`, `hr.group_hr_user`, `hr_timesheet.group_hr_timesheet_user`, `im_livechat.im_livechat_group_user`, `justech_admin_center.group_justech_admin_center_user`, `justech_ecf_core.group_ecf_readonly`, `maintenance.group_equipment_manager`, `marketing_automation.group_marketing_automation_user`, `mass_mailing.group_mass_mailing_user`, `planning.group_planning_user`, `project.group_project_user`, `purchase.group_purchase_user`, `sales_team.group_sale_salesman`, `sign.group_sign_user`, `spreadsheet_dashboard.group_dashboard_manager`, `stock.group_stock_user`

## `documents.group_documents_manager`

- **Nombre:** Documentos / Administrador
- **Implica:** `documents.group_documents_user`
- **Implícito por:** `documents.group_documents_system`

## `documents.group_documents_system`

- **Nombre:** Documentos / Administrador del sistema
- **Implica:** `documents.group_documents_manager`
- **Implícito por:** —

## `documents.group_documents_user`

- **Nombre:** Documentos / Usuario
- **Implica:** `base.group_user`
- **Implícito por:** `documents.group_documents_manager`

## `event.group_event_manager`

- **Nombre:** Eventos / Administrador
- **Implica:** `event.group_event_user`
- **Implícito por:** —

## `event.group_event_registration_desk`

- **Nombre:** Eventos / Módulo de registro
- **Implica:** `base.group_user`
- **Implícito por:** `event.group_event_user`, `sales_team.group_sale_salesman`

## `event.group_event_user`

- **Nombre:** Eventos / Usuario
- **Implica:** `event.group_event_registration_desk`
- **Implícito por:** `event.group_event_manager`

## `helpdesk.group_auto_assignment`

- **Nombre:** Auto asignación
- **Implica:** —
- **Implícito por:** `helpdesk.group_helpdesk_user`

## `helpdesk.group_helpdesk_manager`

- **Nombre:** Soporte al cliente / Administrador
- **Implica:** `helpdesk.group_helpdesk_user`, `mail.group_mail_canned_response_admin`
- **Implícito por:** `base.default_user_group`

## `helpdesk.group_helpdesk_user`

- **Nombre:** Soporte al cliente / Usuario
- **Implica:** `base.group_user`, `helpdesk.group_auto_assignment`, `helpdesk.group_use_sla`, `helpdesk_timesheet.group_use_helpdesk_timesheet`, `website_helpdesk_livechat.group_use_website_helpdesk_livechat`
- **Implícito por:** `helpdesk.group_helpdesk_manager`

## `helpdesk.group_use_sla`

- **Nombre:** Mostrar políticas SLA
- **Implica:** —
- **Implícito por:** `helpdesk.group_helpdesk_user`

## `helpdesk_timesheet.group_use_helpdesk_timesheet`

- **Nombre:** Registro de horas
- **Implica:** —
- **Implícito por:** `helpdesk.group_helpdesk_user`, `hr_timesheet.group_hr_timesheet_user`

## `hr.group_hr_manager`

- **Nombre:** Empleados / Administrador
- **Implica:** `hr.group_hr_user`, `sign.group_sign_user`
- **Implícito por:** `hr_payroll.group_hr_payroll_manager`

## `hr.group_hr_user`

- **Nombre:** Empleados / Encargado: gestionar a todos los empleados
- **Implica:** `base.group_user`, `maintenance.group_equipment_manager`
- **Implícito por:** `hr.group_hr_manager`, `hr_payroll.group_hr_payroll_user`, `hr_timesheet.group_timesheet_manager`

## `hr_payroll.group_hr_payroll_manager`

- **Nombre:** Nómina / Administrador
- **Implica:** `hr.group_hr_manager`, `hr_payroll.group_hr_payroll_user`
- **Implícito por:** —

## `hr_payroll.group_hr_payroll_user`

- **Nombre:** Nómina / Encargado: gestionar todos los contratos
- **Implica:** `hr.group_hr_user`
- **Implícito por:** `hr_payroll.group_hr_payroll_manager`

## `hr_payroll.group_payslip_display`

- **Nombre:** Mostrar recibo de nómina en formato PDF
- **Implica:** —
- **Implícito por:** `base.group_user`

## `hr_timesheet.group_hr_timesheet_approver`

- **Nombre:** Registro de horas / Usuario: todas las hojas de horas
- **Implica:** `hr_timesheet.group_hr_timesheet_user`
- **Implícito por:** `hr_timesheet.group_timesheet_manager`, `project.group_project_manager`

## `hr_timesheet.group_hr_timesheet_user`

- **Nombre:** Registro de horas / Usuario: solo las hojas de horas propias
- **Implica:** `base.group_user`, `helpdesk_timesheet.group_use_helpdesk_timesheet`
- **Implícito por:** `hr_timesheet.group_hr_timesheet_approver`, `industry_fsm.group_fsm_user`

## `hr_timesheet.group_timesheet_manager`

- **Nombre:** Registro de horas / Administrador
- **Implica:** `hr.group_hr_user`, `hr_timesheet.group_hr_timesheet_approver`
- **Implícito por:** —

## `im_livechat.im_livechat_group_manager`

- **Nombre:** Chat en vivo / Administrador
- **Implica:** `im_livechat.im_livechat_group_user`, `mail.group_mail_canned_response_admin`
- **Implícito por:** —

## `im_livechat.im_livechat_group_user`

- **Nombre:** Chat en vivo / Usuario
- **Implica:** `base.group_user`
- **Implícito por:** `im_livechat.im_livechat_group_manager`

## `industry_fsm.group_fsm_manager`

- **Nombre:** Servicio externo / Administrador
- **Implica:** `industry_fsm.group_fsm_user`, `project.group_project_manager`
- **Implícito por:** —

## `industry_fsm.group_fsm_user`

- **Nombre:** Servicio externo / Usuario
- **Implica:** `hr_timesheet.group_hr_timesheet_user`, `project.group_project_user`
- **Implícito por:** `industry_fsm.group_fsm_manager`

## `justech_admin_center.group_justech_admin_center_manager`

- **Nombre:** Administración Justech / Administrador Justech
- **Implica:** `justech_admin_center.group_justech_admin_center_user`, `justech_ecf_core.group_ecf_admin`
- **Implícito por:** `base.group_system`

## `justech_admin_center.group_justech_admin_center_user`

- **Nombre:** Administración Justech / Usuario consola Justech
- **Implica:** `base.group_user`
- **Implícito por:** `justech_admin_center.group_justech_admin_center_manager`

## `justech_ecf_core.group_ecf_admin`

- **Nombre:** Justech e-CF / Administrador e-CF
- **Implica:** `justech_ecf_core.group_ecf_responsible`
- **Implícito por:** `justech_admin_center.group_justech_admin_center_manager`, `justech_fiscal_admin.group_justech_fiscal_admin_manager`

## `justech_ecf_core.group_ecf_auditor`

- **Nombre:** Justech e-CF / Auditor e-CF
- **Implica:** `justech_ecf_core.group_ecf_readonly`
- **Implícito por:** —

## `justech_ecf_core.group_ecf_operator`

- **Nombre:** Justech e-CF / Operador e-CF
- **Implica:** `justech_ecf_core.group_ecf_readonly`
- **Implícito por:** `justech_ecf_core.group_ecf_responsible`

## `justech_ecf_core.group_ecf_readonly`

- **Nombre:** Justech e-CF / Solo lectura e-CF
- **Implica:** `base.group_user`
- **Implícito por:** `justech_ecf_core.group_ecf_auditor`, `justech_ecf_core.group_ecf_operator`

## `justech_ecf_core.group_ecf_responsible`

- **Nombre:** Justech e-CF / Responsable e-CF
- **Implica:** `justech_ecf_core.group_ecf_operator`
- **Implícito por:** `justech_ecf_core.group_ecf_admin`

## `justech_fiscal_admin.group_justech_fiscal_admin_manager`

- **Nombre:** Contabilidad / Administrador Fiscal
- **Implica:** `justech_ecf_core.group_ecf_admin`, `justech_fiscal_admin.group_justech_fiscal_admin_user`, `justech_l10n_do_base.group_justech_do_fiscal_manager`, `justech_l10n_do_payments_withholding.group_justech_withholding_catalog_admin`
- **Implícito por:** `base.group_system`

## `justech_fiscal_admin.group_justech_fiscal_admin_user`

- **Nombre:** Contabilidad / Fiscal Admin / Lectura
- **Implica:** `justech_l10n_do_base.group_justech_do_fiscal_user`
- **Implícito por:** `justech_fiscal_admin.group_justech_fiscal_admin_manager`

## `justech_global_audit_log.group_audit_user`

- **Nombre:** Auditoría / Usuario
- **Implica:** —
- **Implícito por:** `justech_global_audit_log.group_justech_audit_manager`

## `justech_global_audit_log.group_justech_audit_manager`

- **Nombre:** Auditoría / Administrador
- **Implica:** `justech_global_audit_log.group_audit_user`
- **Implícito por:** `base.group_erp_manager`, `base.group_system`

## `justech_l10n_do_base.group_justech_do_fiscal_manager`

- **Nombre:** Contabilidad / Responsable Fiscal
- **Implica:** `justech_l10n_do_base.group_justech_do_fiscal_user`
- **Implícito por:** `justech_fiscal_admin.group_justech_fiscal_admin_manager`

## `justech_l10n_do_base.group_justech_do_fiscal_user`

- **Nombre:** Contabilidad / Usuario Fiscal
- **Implica:** `account.group_account_invoice`
- **Implícito por:** `justech_fiscal_admin.group_justech_fiscal_admin_user`, `justech_l10n_do_base.group_justech_do_fiscal_manager`, `justech_l10n_do_payments_withholding.group_justech_withholding_catalog_admin`

## `justech_l10n_do_payments_withholding.group_justech_withholding_catalog_admin`

- **Nombre:** Contabilidad / Administrador de Retenciones
- **Implica:** `justech_l10n_do_base.group_justech_do_fiscal_user`
- **Implícito por:** `account.group_account_manager`, `justech_fiscal_admin.group_justech_fiscal_admin_manager`

## `justech_modules.group_justech_internal_admin`

- **Nombre:** Justech Platform / Justech Internal Admin
- **Implica:** `justech_modules.group_justech_license_manager`
- **Implícito por:** —

## `justech_modules.group_justech_license_manager`

- **Nombre:** Justech Platform / Justech License Manager
- **Implica:** `justech_modules.group_justech_license_user`
- **Implícito por:** `justech_modules.group_justech_internal_admin`

## `justech_modules.group_justech_license_user`

- **Nombre:** Justech Platform / Justech License User
- **Implica:** —
- **Implícito por:** `justech_modules.group_justech_license_manager`, `justech_modules.group_justech_support`

## `justech_modules.group_justech_support`

- **Nombre:** Justech Platform / Justech Support
- **Implica:** `justech_modules.group_justech_license_user`
- **Implícito por:** —

## `justech_recurring_fee.group_recurring_fee_manager`

- **Nombre:** Fees recurrentes / Responsable Fees
- **Implica:** `justech_recurring_fee.group_recurring_fee_user`
- **Implícito por:** `base.group_system`

## `justech_recurring_fee.group_recurring_fee_user`

- **Nombre:** Fees recurrentes / Usuario Fees
- **Implica:** `sales_team.group_sale_salesman`
- **Implícito por:** `justech_recurring_fee.group_recurring_fee_manager`

## `justech_warranty.group_warranty_manager`

- **Nombre:** Garantías / Responsable de Garantías
- **Implica:** `justech_warranty.group_warranty_user`
- **Implícito por:** `base.group_erp_manager`, `base.group_system`

## `justech_warranty.group_warranty_user`

- **Nombre:** Garantías / Usuario de Garantías
- **Implica:** —
- **Implícito por:** `justech_warranty.group_warranty_manager`

## `l10n_do_accounting.group_l10n_do_debit_note`

- **Nombre:** Can create Debit Notes
- **Implica:** `account.group_account_invoice`
- **Implícito por:** —

## `l10n_do_accounting.group_l10n_do_fiscal_credit_note`

- **Nombre:** Puede crear Notas de Crédito Fiscales
- **Implica:** `account.group_account_invoice`
- **Implícito por:** —

## `l10n_do_accounting.group_l10n_do_fiscal_invoice_cancel`

- **Nombre:** Puede cancelar Facturas Fiscales
- **Implica:** `account.group_account_invoice`
- **Implícito por:** —

## `mail.group_mail_canned_response_admin`

- **Nombre:** Respuestas predefinidas / Administrador de la respuesta predefinida
- **Implica:** —
- **Implícito por:** `base.group_system`, `helpdesk.group_helpdesk_manager`, `im_livechat.im_livechat_group_manager`, `project.group_project_manager`, `sales_team.group_sale_manager`

## `mail.group_mail_template_editor`

- **Nombre:** Editor de plantillas de correo
- **Implica:** —
- **Implícito por:** `base.group_system`

## `maintenance.group_equipment_manager`

- **Nombre:** Mantenimiento / Responsable de los equipos
- **Implica:** `base.group_user`
- **Implícito por:** `hr.group_hr_user`

## `marketing_automation.group_marketing_automation_user`

- **Nombre:** Automatización de marketing / Usuario
- **Implica:** `base.group_user`, `mass_mailing.group_mass_mailing_user`
- **Implícito por:** —

## `mass_mailing.group_mass_mailing_user`

- **Nombre:** Marketing por correo / Usuario
- **Implica:** `base.group_user`
- **Implícito por:** `marketing_automation.group_marketing_automation_user`

## `planning.group_planning_manager`

- **Nombre:** Planeación / Administrador
- **Implica:** `planning.group_planning_user`
- **Implícito por:** —

## `planning.group_planning_user`

- **Nombre:** Planeación / Usuario
- **Implica:** `base.group_user`
- **Implícito por:** `planning.group_planning_manager`

## `product.group_product_manager`

- **Nombre:** Productos / Crear
- **Implica:** —
- **Implícito por:** `base.group_system`

## `product.group_product_pricelist`

- **Nombre:** Listas de precios básicas
- **Implica:** —
- **Implícito por:** `base.group_user`

## `product.group_product_variant`

- **Nombre:** Administrar variantes de productos
- **Implica:** —
- **Implícito por:** `base.group_user`

## `project.group_project_manager`

- **Nombre:** Proyecto / Administrador
- **Implica:** `hr_timesheet.group_hr_timesheet_approver`, `mail.group_mail_canned_response_admin`, `project.group_project_user`
- **Implícito por:** `industry_fsm.group_fsm_manager`

## `project.group_project_stages`

- **Nombre:** Use etapas en el proyecto
- **Implica:** —
- **Implícito por:** `base.group_user`

## `project.group_project_user`

- **Nombre:** Proyecto / Usuario
- **Implica:** `base.group_user`
- **Implícito por:** `industry_fsm.group_fsm_user`, `project.group_project_manager`

## `purchase.group_purchase_manager`

- **Nombre:** Compras / Administrador
- **Implica:** `purchase.group_purchase_user`
- **Implícito por:** —

## `purchase.group_purchase_user`

- **Nombre:** Compras / Usuario
- **Implica:** `base.group_user`
- **Implícito por:** `purchase.group_purchase_manager`

## `purchase.group_send_reminder`

- **Nombre:** Envíe un correo electrónico de recordatorio automático para confirmar la entrega
- **Implica:** —
- **Implícito por:** `base.group_user`

## `sale.group_discount_per_so_line`

- **Nombre:** Descuento en líneas
- **Implica:** —
- **Implícito por:** `base.group_user`

## `sale.group_proforma_sales`

- **Nombre:** Facturas proforma
- **Implica:** —
- **Implícito por:** `base.group_user`

## `sale_management.group_sale_order_template`

- **Nombre:** Plantillas de cotización
- **Implica:** —
- **Implícito por:** `base.group_user`

## `sales_team.group_sale_manager`

- **Nombre:** Ventas / Administrador
- **Implica:** `mail.group_mail_canned_response_admin`, `sales_team.group_sale_salesman_all_leads`
- **Implícito por:** —

## `sales_team.group_sale_salesman`

- **Nombre:** Ventas / Usuario: solo mostrar documentos propios
- **Implica:** `base.group_user`, `event.group_event_registration_desk`
- **Implícito por:** `justech_recurring_fee.group_recurring_fee_user`, `sales_team.group_sale_salesman_all_leads`

## `sales_team.group_sale_salesman_all_leads`

- **Nombre:** Ventas / Usuario: todos los documentos
- **Implica:** `sales_team.group_sale_salesman`
- **Implícito por:** `sales_team.group_sale_manager`

## `sign.group_sign_manager`

- **Nombre:** Firma electrónica / Administrador
- **Implica:** `sign.group_sign_user`
- **Implícito por:** —

## `sign.group_sign_user`

- **Nombre:** Firma electrónica / Usuario: plantillas propias
- **Implica:** `base.group_user`
- **Implícito por:** `hr.group_hr_manager`, `sign.group_sign_manager`

## `spreadsheet_dashboard.group_dashboard_manager`

- **Nombre:** Tablero / Admin
- **Implica:** `base.group_user`
- **Implícito por:** —

## `stock.group_lot_on_delivery_slip`

- **Nombre:** Mostrar número de lote y serie en los recibos de entrega
- **Implica:** —
- **Implícito por:** `base.group_portal`, `base.group_user`

## `stock.group_production_lot`

- **Nombre:** Gestionar números de lote y de serie
- **Implica:** —
- **Implícito por:** `base.group_portal`, `base.group_user`

## `stock.group_stock_manager`

- **Nombre:** Inventario / Administrador
- **Implica:** `stock.group_stock_user`
- **Implícito por:** —

## `stock.group_stock_multi_locations`

- **Nombre:** Gestionar múltiples ubicaciones de existencias
- **Implica:** —
- **Implícito por:** `base.group_user`

## `stock.group_stock_user`

- **Nombre:** Inventario / Usuario
- **Implica:** `base.group_user`
- **Implícito por:** `stock.group_stock_manager`

## `stock_account.group_lot_on_invoice`

- **Nombre:** Mostrar el número de serie y lote en las facturas
- **Implica:** —
- **Implícito por:** `base.group_user`

## `survey.group_survey_manager`

- **Nombre:** Encuestas / Administrador
- **Implica:** `survey.group_survey_user`
- **Implícito por:** —

## `survey.group_survey_user`

- **Nombre:** Encuestas / Usuario
- **Implica:** —
- **Implícito por:** `survey.group_survey_manager`

## `uom.group_uom`

- **Nombre:** Gestionar varias unidades de medida
- **Implica:** —
- **Implícito por:** `base.group_user`

## `website.group_multi_website`

- **Nombre:** Sitio web múltiple
- **Implica:** —
- **Implícito por:** `base.group_portal`, `base.group_public`, `base.group_user`

## `website.group_website_designer`

- **Nombre:** Sitio web / Editor y diseñador
- **Implica:** `base.group_sanitize_override`, `website.group_website_restricted_editor`
- **Implícito por:** `base.group_system`

## `website.group_website_restricted_editor`

- **Nombre:** Sitio web / Editor restringido
- **Implica:** —
- **Implícito por:** `website.group_website_designer`

## `website.website_page_controller_expose`

- **Nombre:** Acceso público a un modelo arbitrario
- **Implica:** —
- **Implícito por:** `base.group_portal`, `base.group_public`

## `website_helpdesk_livechat.group_use_website_helpdesk_livechat`

- **Nombre:** Usar chat en vivo
- **Implica:** —
- **Implícito por:** `helpdesk.group_helpdesk_user`

