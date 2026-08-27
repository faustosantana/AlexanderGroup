# -*- coding: utf-8 -*-
"""Singleton Centro Fiscal + limpieza de residuos transient."""


def migrate(cr, version):
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'justech_fiscal_admin_center'
        )
        """
    )
    if not cr.fetchone()[0]:
        return
    # Conservar el id mínimo por company_id y eliminar el resto
    cr.execute(
        """
        DELETE FROM justech_fiscal_admin_center
        WHERE id NOT IN (
            SELECT MIN(id) FROM justech_fiscal_admin_center
            GROUP BY company_id
        )
        """
    )
    # Quitar herencia Account Manager → Fiscal Admin Manager (SoD)
    cr.execute(
        """
        DELETE FROM res_groups_implied_rel
        WHERE gid = (SELECT res_id FROM ir_model_data
                     WHERE module='account' AND name='group_account_manager' LIMIT 1)
          AND hid = (SELECT res_id FROM ir_model_data
                     WHERE module='justech_fiscal_admin'
                       AND name='group_justech_fiscal_admin_manager' LIMIT 1)
        """
    )
