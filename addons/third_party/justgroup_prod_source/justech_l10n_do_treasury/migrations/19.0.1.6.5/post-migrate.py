# -*- coding: utf-8 -*-
"""HOTFIX 2026.1.4 — recalcular estado bancario de pagos amount<=0."""


def migrate(cr, version):
    # Falso positivo: líneas a 0 quedan reconciled sin extracto.
    cr.execute(
        """
        UPDATE account_payment
           SET treasury_bank_state = 'bank_pending'
         WHERE COALESCE(amount, 0) <= 0
           AND state IN ('in_process', 'paid')
           AND treasury_bank_state = 'bank_reconciled'
        """
    )
