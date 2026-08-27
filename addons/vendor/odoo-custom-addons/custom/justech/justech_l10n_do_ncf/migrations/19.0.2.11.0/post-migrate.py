# -*- coding: utf-8 -*-
"""Etiquetas UX Compras: action RFQ (Odoo 19 name jsonb)."""
import json


def migrate(cr, version):
    cr.execute(
        """
        SELECT res_id FROM ir_model_data
        WHERE module = 'purchase' AND name = 'purchase_rfq'
          AND model = 'ir.actions.act_window'
        LIMIT 1
        """
    )
    row = cr.fetchone()
    if not row:
        return
    action_id = row[0]
    label = "Solicitudes de Orden"
    cr.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name IN ('ir_act_window', 'ir_actions_act_window')
        """
    )
    tables = [r[0] for r in cr.fetchall()]
    for table in tables:
        cr.execute(
            """
            SELECT data_type FROM information_schema.columns
            WHERE table_name = %s AND column_name = 'name'
            """,
            (table,),
        )
        dtype = (cr.fetchone() or [None])[0]
        if dtype == "jsonb":
            payload = json.dumps({"en_US": label, "es_DO": label, "es_ES": label})
            cr.execute(
                f"UPDATE {table} SET name = COALESCE(name, '{{}}'::jsonb) || %s::jsonb WHERE id = %s",
                (payload, action_id),
            )
        else:
            cr.execute(
                f"UPDATE {table} SET name = %s WHERE id = %s",
                (label, action_id),
            )
