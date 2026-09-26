# 18 — Known pending (real only)

BLOCKING: none.

NON_BLOCKING:

1. Doralex B13 range 35 is active in DB (next=17). Policy: do not use until DGII confirmation. Not changed.
2. Blue Elite B15 exhausted (next=102).
3. B17 missing all companies.
4. B1300000016 / INV/2026/00021 missing PDF (0 attachments).
5. Product 1613 duplicate `Servicios profesionales` (consu, price 1.00, used on 1 SO/AML). Canonical 168 remains service 0.00.
6. Product 1641 BARRENA HSS purchase_ok=False (1 SO). Left unchanged.
7. No automated backup cron — restore of today's manual backup PASSed.
8. Staging leftover draft PO `DOR/OC/00004` still has mixed taxes (72 rel). Production CROSS=0.
9. Company bank account not trusted blocks invoice post on staging (Geilin UserError / Alexander RedirectWarning). Business config, not ACL.
10. Manual-review product types: opening placeholder 167 + DX smoke/test services.
11. wkhtmltopdf container network warning during render (PDFs still produced).

Closed, do not reopen: opening import, product master, phase 2, grava duplicate cleanup, multicompany tax fix.
