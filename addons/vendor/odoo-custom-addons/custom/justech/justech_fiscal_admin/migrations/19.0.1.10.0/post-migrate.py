# -*- coding: utf-8 -*-
"""RC-002 / P0.1 — Disable NCF dual-write (FISC-AUD-001).

Emitted NCF SoT = Justech; received vendor NCF = LATAM.
Does not modify historical moves or NCF alert baseline.
Idempotent.
"""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE justech_fiscal_feature_flag
           SET enabled = false,
               readonly_flag = false,
               description = jsonb_build_object(
                   'en_US',
                   'RC-002/P0.1 OFF: mirror Justech→LATAM NCF. Emitted SoT=Justech; '
                   'received purchases=LATAM. Reactivate only with approval.'
               )
         WHERE code = 'ncf_dual_write'
        """
    )
