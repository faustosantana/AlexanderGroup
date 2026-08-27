# -*- coding: utf-8 -*-
def migrate(cr, version):
    """Cron padrón: horario + inactivo hasta habilitar auto_update."""
    cr.execute(
        """
        UPDATE ir_cron
           SET interval_number = 1,
               interval_type = 'hours',
               active = FALSE
         WHERE id = (
            SELECT res_id FROM ir_model_data
             WHERE module = 'justech_l10n_do_base'
               AND name = 'ir_cron_justech_rnc_padron_auto_update'
             LIMIT 1
         )
        """
    )
