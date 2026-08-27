# Justech Dominican NCF

NCF ranges, automatic assignment, validations and invoice PDF.

## Architecture (Phase 3A)

Business logic extracted to `services/`:

- `justech.do.ncf.document.type.resolver.service`
- `justech.do.ncf.duplicate.service`
- `justech.do.ncf.assignment.service`

`account.move` keeps `_justech_*` API as thin wrappers (zero functional change).

See `ARCHITECTURE.md`, `diagrams/`, `MIGRATION.md`.

## Dependencies

- `justech_l10n_do_base`
- `account_debit_note`

## Configuration

1. Install after `justech_l10n_do_base`
2. Enable **Use NCF** on sales/purchase journals
3. Create and activate NCF ranges per document type
4. Post invoices — NCF assigned automatically for B01/B02/B04/B11/B13
