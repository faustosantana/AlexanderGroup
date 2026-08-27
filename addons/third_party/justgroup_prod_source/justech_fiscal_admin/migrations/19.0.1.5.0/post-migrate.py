# -*- coding: utf-8 -*-
"""Roles fiscales SoD + singleton por empresa."""


def migrate(cr, version):
    # Quitar implied Account → Fiscal User / Fiscal Admin
    cr.execute(
        """
        DELETE FROM res_groups_implied_rel
        WHERE gid IN (
            SELECT res_id FROM ir_model_data
            WHERE module='account' AND name IN ('group_account_manager','group_account_user')
        )
        AND hid IN (
            SELECT res_id FROM ir_model_data
            WHERE (module='justech_l10n_do_base' AND name='group_justech_do_fiscal_user')
               OR (module='justech_fiscal_admin' AND name='group_justech_fiscal_admin_manager')
        )
        """
    )
    # Responsable Fiscal NO implica Administrador Fiscal
    cr.execute(
        """
        DELETE FROM res_groups_implied_rel
        WHERE gid = (SELECT res_id FROM ir_model_data
                     WHERE module='justech_l10n_do_base'
                       AND name='group_justech_do_fiscal_manager' LIMIT 1)
          AND hid = (SELECT res_id FROM ir_model_data
                     WHERE module='justech_fiscal_admin'
                       AND name='group_justech_fiscal_admin_manager' LIMIT 1)
        """
    )
    # Singleton cleanup
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'justech_fiscal_admin_center'
        )
        """
    )
    if cr.fetchone()[0]:
        cr.execute(
            """
            DELETE FROM justech_fiscal_admin_center
            WHERE id NOT IN (
                SELECT MIN(id) FROM justech_fiscal_admin_center GROUP BY company_id
            )
            """
        )
