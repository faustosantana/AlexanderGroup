"""Crea configs B11/B13/B17 por empresa sin inventar rangos; modo recibido histórico."""


def migrate(cr, version):
    # Histórico de compras: registro recibido (LATAM). No tocar posted.
    cr.execute(
        """
        UPDATE account_move
           SET justech_do_purchase_registration_mode = 'received'
         WHERE move_type IN ('in_invoice', 'in_refund', 'in_receipt')
           AND (
                justech_do_purchase_registration_mode IS NULL
                OR justech_do_purchase_registration_mode = ''
           )
        """
    )
    # Configs por empresa × tipo compra (sin crear rangos). Populate related cols.
    cr.execute(
        """
        INSERT INTO justech_do_purchase_emission_config
            (company_id, document_type_id, prefix, code, name_full,
             allows_purchase_emission, create_uid, write_uid, create_date, write_date)
        SELECT c.id,
               d.id,
               d.prefix,
               d.code,
               d.prefix || ' — ' || COALESCE(
                    d.name->>'en_US',
                    d.name->>'es_DO',
                    d.name::text,
                    d.prefix
               ),
               TRUE,
               1, 1, NOW(), NOW()
          FROM res_company c
          CROSS JOIN justech_do_fiscal_document_type d
         WHERE d.prefix IN ('B11', 'B13', 'B17')
           AND NOT EXISTS (
                SELECT 1 FROM justech_do_purchase_emission_config cfg
                 WHERE cfg.company_id = c.id
                   AND cfg.document_type_id = d.id
           )
        """
    )
    # Backfill related fields if insert previo dejó vacíos.
    cr.execute(
        """
        UPDATE justech_do_purchase_emission_config cfg
           SET prefix = d.prefix,
               code = d.code,
               name_full = d.prefix || ' — ' || COALESCE(
                    d.name->>'en_US', d.name->>'es_DO', d.name::text, d.prefix
               )
          FROM justech_do_fiscal_document_type d
         WHERE d.id = cfg.document_type_id
           AND (cfg.prefix IS NULL OR cfg.prefix = '' OR cfg.name_full IS NULL OR cfg.name_full = '')
        """
    )
