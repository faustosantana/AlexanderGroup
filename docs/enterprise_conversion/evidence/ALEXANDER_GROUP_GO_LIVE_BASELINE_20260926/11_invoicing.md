# 11 — Invoicing

PROD customer invoices: posted 27 / draft 1 / cancel 1.

Staging E2E created **draft** invoices only (rolled back). invoice_tax_ok True on all 6.

Geilin: can create customer invoice; not Accounting Admin; not Settings. Post on staging blocked by company bank-trust UserError (business, not ACL).

Operators Janny/Leopordo: AccessError on `action_post` ("You don't have the access rights to post an invoice.").

Alexander: invoice create allowed; post RedirectWarning on untrusted bank account.

B1300000016 / INV/2026/00021 (id 141) posted, 0 PDF attachments — NON_BLOCKING, not rewritten.
