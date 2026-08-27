"""RC6.1: alinear catálogo legacy RET5% con elegibilidad 623."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE justech_do_withholding_catalog
           SET affects_623 = TRUE,
               affects_607 = TRUE,
               dgii_withholding_code = COALESCE(NULLIF(dgii_withholding_code, ''), '07'),
               rate = CASE WHEN COALESCE(rate, 0) = 0 THEN 5.0 ELSE rate END,
               withholding_type = COALESCE(withholding_type, 'isr')
         WHERE code IN ('RET5%', 'RET-GOB-5', 'wh_isr_gov')
        """
    )
    # Recalcular related storeados en líneas existentes (sin tocar importes/asientos).
    cr.execute(
        """
        UPDATE justech_payment_withholding_line wh
           SET affects_623 = c.affects_623,
               affects_606 = c.affects_606,
               affects_607 = c.affects_607,
               dgii_withholding_code = c.dgii_withholding_code,
               fiscal_report_codes = CONCAT_WS(
                   '/',
                   CASE WHEN c.affects_606 THEN '606' END,
                   CASE WHEN c.affects_607 THEN '607' END,
                   CASE WHEN c.affects_623 OR c.code IN ('RET5%', 'RET-GOB-5', 'wh_isr_gov')
                        THEN '623' END
               )
          FROM justech_do_withholding_catalog c
         WHERE wh.catalog_id = c.id
           AND c.code IN ('RET5%', 'RET-GOB-5', 'wh_isr_gov')
        """
    )
