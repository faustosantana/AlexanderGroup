"""RC6: catálogo retenciones global + índice único por alcance."""


def migrate(cr, version):
    cr.execute(
        """
        ALTER TABLE justech_do_withholding_catalog
            ALTER COLUMN company_id DROP NOT NULL
        """
    )
    cr.execute(
        """
        ALTER TABLE justech_do_withholding_catalog
            DROP CONSTRAINT IF EXISTS justech_do_withholding_catalog_justech_wh_catalog_code_company_uniq
        """
    )
    cr.execute(
        """
        ALTER TABLE justech_do_withholding_catalog
            DROP CONSTRAINT IF EXISTS justech_wh_catalog_code_company_uniq
        """
    )
    # Índice único COALESCE(company_id,0) — globales compartidas
    cr.execute("DROP INDEX IF EXISTS justech_wh_catalog_code_scope_uniq")
    cr.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS justech_wh_catalog_code_scope_uniq
        ON justech_do_withholding_catalog (code, COALESCE(company_id, 0))
        """
    )
    # Columnas nuevas (si el ORM aún no las creó en este paso)
    cr.execute(
        """
        ALTER TABLE justech_do_withholding_catalog
            ADD COLUMN IF NOT EXISTS source_tax_name VARCHAR
        """
    )
    cr.execute(
        """
        ALTER TABLE justech_do_withholding_catalog
            ADD COLUMN IF NOT EXISTS source_tax_use VARCHAR
        """
    )
