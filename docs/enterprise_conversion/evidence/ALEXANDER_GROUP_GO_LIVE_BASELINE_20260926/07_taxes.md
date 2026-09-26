# 07 — Taxes

PROD live documents:

- CROSS_SALE = 0
- CROSS_PO = 0
- CROSS_INV = 0
- CROSS_COMPANY_TAX_REFERENCE = 0

Staging leftover: 72 cross-company tax rows on draft `DOR/OC/00004` (pre-existing QA PO, not production). Not cleaned in this closeout.

Multicompany tax fix already deployed (`justech_alexander_base` 19.0.1.0.15). Revalidated. Tax record rule unchanged.

Each company E2E SO/PO used that company's 18% ITBIS only.
