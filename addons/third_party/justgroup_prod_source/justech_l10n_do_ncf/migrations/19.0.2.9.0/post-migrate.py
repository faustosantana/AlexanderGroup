"""Enlazar códigos Adel l10n_do_expense_type → justech.do.dgii.expense.type.

Idempotente. No altera NCF, rangos ni facturas publicadas más allá del M2O.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'account_move'
          AND column_name = 'justech_do_expense_type_id'
        """
    )
    if not cr.fetchone():
        _logger.info("post-migrate 19.0.2.9.0: skip — column missing")
        return

    cr.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'account_move'
          AND column_name = 'l10n_do_expense_type'
        """
    )
    if not cr.fetchone():
        _logger.info("post-migrate 19.0.2.9.0: skip — no l10n_do_expense_type")
        return

    cr.execute(
        """
        UPDATE account_move AS m
           SET justech_do_expense_type_id = t.id
          FROM justech_do_dgii_expense_type AS t
         WHERE m.justech_do_expense_type_id IS NULL
           AND m.l10n_do_expense_type IS NOT NULL
           AND m.l10n_do_expense_type = t.code
           AND m.move_type IN ('in_invoice', 'in_refund')
        """
    )
    _logger.info(
        "post-migrate 19.0.2.9.0: linked expense types on %s moves",
        cr.rowcount,
    )
