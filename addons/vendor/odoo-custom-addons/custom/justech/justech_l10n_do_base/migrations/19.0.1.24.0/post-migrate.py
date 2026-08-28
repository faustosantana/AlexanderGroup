"""Actualiza nombres funcionales B11/B13 (noupdate data)."""


def migrate(cr, version):
    cr.execute(
        """
        SELECT data_type FROM information_schema.columns
         WHERE table_name='justech_do_fiscal_document_type' AND column_name='name'
        """
    )
    row = cr.fetchone()
    dtype = (row and row[0]) or "character varying"
    if dtype == "jsonb":
        cr.execute(
            """
            UPDATE justech_do_fiscal_document_type
               SET name = jsonb_set(
                    COALESCE(name, '{}'::jsonb),
                    '{en_US}',
                    '"Comprobante de Compras / Proveedor Informal"'
               )
             WHERE prefix = 'B11'
            """
        )
        cr.execute(
            """
            UPDATE justech_do_fiscal_document_type
               SET name = jsonb_set(
                    COALESCE(name, '{}'::jsonb),
                    '{en_US}',
                    '"Comprobante para Gastos Menores"'
               )
             WHERE prefix = 'B13'
            """
        )
    else:
        cr.execute(
            """
            UPDATE justech_do_fiscal_document_type
               SET name = 'Comprobante de Compras / Proveedor Informal'
             WHERE prefix = 'B11'
            """
        )
        cr.execute(
            """
            UPDATE justech_do_fiscal_document_type
               SET name = 'Comprobante para Gastos Menores'
             WHERE prefix = 'B13'
            """
        )
