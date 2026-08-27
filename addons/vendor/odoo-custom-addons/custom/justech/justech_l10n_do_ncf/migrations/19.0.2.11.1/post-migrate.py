# -*- coding: utf-8 -*-
"""Limpia partner_ref solo cuando era copia inequívoca del nombre de cotización."""


def migrate(cr, version):
    # Preview-equivalent apply: partner_ref == origin == sale.order.name (misma empresa).
    # No toca valores ambiguos ni referencias sin SO matching.
    cr.execute(
        """
        UPDATE purchase_order po
           SET partner_ref = NULL,
               write_date = (now() at time zone 'utc'),
               write_uid = 1
          FROM sale_order so
         WHERE po.partner_ref IS NOT NULL
           AND po.partner_ref <> ''
           AND po.origin IS NOT NULL
           AND po.origin = po.partner_ref
           AND so.name = po.partner_ref
           AND so.company_id = po.company_id
           AND NOT EXISTS (
                SELECT 1 FROM sale_order so2
                 WHERE so2.name = po.partner_ref
                   AND so2.company_id = po.company_id
                   AND so2.id <> so.id
           )
        """
    )
