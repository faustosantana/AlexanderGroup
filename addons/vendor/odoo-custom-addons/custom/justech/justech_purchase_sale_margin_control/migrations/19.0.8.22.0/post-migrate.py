# -*- coding: utf-8 -*-
"""Deactivate legacy margin menus removed from menus.xml (upgrade-only cleanup).

Fresh installs never create these menus. Upgraded databases may still have them
from releases before 8.22; this migration idempotently hides them.
"""
import logging

_logger = logging.getLogger(__name__)

LEGACY_MENU_XML_NAMES = (
    "menu_purchase_sale_margin_report_wizard",
    "menu_purchase_sale_payable_auxiliary_pending_relation",
    "menu_purchase_sale_payable_auxiliary_pending_payment",
    "menu_purchase_sale_payable_auxiliary_paid",
    "menu_purchase_sale_payable_auxiliary_no_sale",
    "menu_purchase_sale_payable_auxiliary_differences",
    "menu_purchase_sale_payable_auxiliary_closed",
    "menu_purchase_sale_payable_auxiliary_pending_invoice",
    "menu_purchase_sale_margin_transaction_negative_margins",
    "menu_purchase_sale_pending_links",
    "menu_purchase_sale_margin_tools",
)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        UPDATE ir_ui_menu AS m
           SET active = FALSE
          FROM ir_model_data AS d
         WHERE d.model = 'ir.ui.menu'
           AND d.res_id = m.id
           AND d.module = 'justech_purchase_sale_margin_control'
           AND d.name = ANY(%s)
           AND m.active = TRUE
        """,
        (list(LEGACY_MENU_XML_NAMES),),
    )
    if cr.rowcount:
        _logger.info(
            "justech_purchase_sale_margin_control 8.22: deactivated %s legacy menu(s)",
            cr.rowcount,
        )
