"""Catálogo de las 6 personas. Sin contraseñas ni secretos."""

from __future__ import annotations

M365_DOMAIN = "inversionesdoralex.com"
OPERATIONAL_COMPANY_IDS = (8, 9, 10, 11, 12, 13)
DEFAULT_COMPANY_ID = 11  # INVERSIONES DORALEX

PEOPLE = (
    {
        "key": "luis",
        "display_name": "Luis Joel Aquino Casado",
        "given": "Luis Joel",
        "surname": "Aquino Casado",
        "upn": "luis.aquino@inversionesdoralex.com",
        "mail_nickname": "luis.aquino",
        "role": "SALES_PURCHASE",
        "odoo_admin": False,
        "invoicing": False,
        "search_needles": ("luis.aquino", "Luis Joel Aquino", "Luis Joel"),
    },
    {
        "key": "janny",
        "display_name": "Janny Chantal Montero",
        "given": "Janny Chantal",
        "surname": "Montero",
        "upn": "janny.montero@inversionesdoralex.com",
        "mail_nickname": "janny.montero",
        "role": "SALES_PURCHASE",
        "odoo_admin": False,
        "invoicing": False,
        "search_needles": ("janny.montero", "Janny Chantal", "Janny"),
    },
    {
        "key": "elianny",
        "display_name": "Elianny Nicole Sanchez Javier",
        "given": "Elianny Nicole",
        "surname": "Sanchez Javier",
        "upn": "elianny.sanchez@inversionesdoralex.com",
        "mail_nickname": "elianny.sanchez",
        "role": "SALES_PURCHASE",
        "odoo_admin": False,
        "invoicing": False,
        "search_needles": ("elianny.sanchez", "Elianny Nicole", "Elianny"),
    },
    {
        "key": "leopordo",
        "display_name": "Leopordo Jimenez",
        "given": "Leopordo Jimenez",
        "surname": "Jimenez",
        "upn": "leopordo.jimenez@inversionesdoralex.com",
        "mail_nickname": "leopordo.jimenez",
        "role": "SALES_PURCHASE",
        "odoo_admin": False,
        "invoicing": False,
        "search_needles": ("leopordo.jimenez", "Leopordo"),
    },
    {
        "key": "alexander",
        "display_name": "Alexander Pina Aquino",
        "given": "Alexander",
        "surname": "Pina Aquino",
        "upn": "alexander.pina@inversionesdoralex.com",
        "mail_nickname": "alexander.pina",
        "role": "ODOO_ADMIN",
        "odoo_admin": True,
        "invoicing": True,
        "search_needles": (
            "alexander.pina",
            "inversionesdoralex@gmail.com",
            "Alexander Piña",
            "Alexander Pina",
        ),
        "known_odoo_login": "inversionesdoralex@gmail.com",
        "do_not_reset_m365_if_existing": True,
        "related_m365": (
            "admin@doralex.onmicrosoft.com",
            "alex@doralex.onmicrosoft.com",
        ),
    },
    {
        "key": "geilin",
        "display_name": "Geilin Rosario Suero",
        "given": "Geilin",
        "surname": "Rosario Suero",
        "upn": "geilin.rosario@inversionesdoralex.com",
        "mail_nickname": "geilin.rosario",
        "role": "INVOICING",
        "odoo_admin": False,
        "invoicing": True,
        "search_needles": ("geilin.rosario", "Geilin Rosario", "Geilin"),
    },
)

# Exchange Online Kiosk part number. No inventar SKU_ID.
KIOSK_PART_NUMBERS = ("EXCHANGEDESKLESS",)

# Licencias que ya incluyen Exchange de buzón real (no quitar / no degradar).
SUPERIOR_EXCHANGE_PART_NUMBERS = (
    "EXCHANGESTANDARD",
    "EXCHANGEENTERPRISE",
    "O365_BUSINESS_PREMIUM",
    "O365_BUSINESS_ESSENTIALS",
    "SPB",
    "SPE_E3",
    "SPE_E5",
    "ENTERPRISEPACK",
    "ENTERPRISEPREMIUM",
    "STANDARDPACK",
)

DO_NOT_TOUCH_M365 = (
    "admin@doralex.onmicrosoft.com",
    "alex@doralex.onmicrosoft.com",
)

SALES_PURCHASE_GROUPS = (
    "sales_team.group_sale_salesman_all_leads",
    "purchase.group_purchase_user",
    "stock.group_stock_user",
    "base.group_partner_manager",
    "justech_purchase_sale_margin_control.group_margin_sales",
    "justech_purchase_sale_margin_control.group_margin_purchase",
    "justech_sale_purchase_trace.group_justech_trace_purchase",
)

INVOICING_EXTRA_GROUPS = (
    "account.group_account_invoice",
    "justech_l10n_do_base.group_justech_do_fiscal_user",
)

ALEXANDER_ADMIN_GROUPS = (
    "base.group_system",
    "base.group_erp_manager",
    "sales_team.group_sale_manager",
    "purchase.group_purchase_manager",
    "account.group_account_manager",
    "stock.group_stock_manager",
    "justech_l10n_do_base.group_justech_do_fiscal_manager",
    "justech_approval_flow.group_approver",
    "justech_purchase_sale_margin_control.group_margin_admin",
    "justech_sale_purchase_trace.group_justech_trace_manager",
)

FORBIDDEN_OPERATOR_GROUPS = (
    "base.group_system",
    "base.group_erp_manager",
    "account.group_account_manager",
    "justech_l10n_do_base.group_justech_do_fiscal_manager",
    "justech_approval_flow.group_self_approve",
    "justech_approval_flow.group_manager",
)

FORBIDDEN_SALES_ONLY_GROUPS = FORBIDDEN_OPERATOR_GROUPS + (
    "account.group_account_invoice",
    "justech_l10n_do_base.group_justech_do_fiscal_user",
)
