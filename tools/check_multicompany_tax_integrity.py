#!/usr/bin/env python3
"""Diagnóstico idempotente de impuestos multiempresa.

Uso (odoo shell):

    python3 /usr/bin/odoo shell --database=... < tools/check_multicompany_tax_integrity.py

No escribe datos. No toca NCF, mail, DGII ni e-CF.
"""

env = env  # noqa: F821

service = env["justech.alexander.multicompany.tax.service"]
report = service.check_multicompany_tax_integrity()
print("=== check_multicompany_tax_integrity ===")
for key, value in report.items():
    if key == "counts":
        print("COUNTS", value)
        continue
    print(key, len(value) if isinstance(value, list) else value)
print("DRY_RUN_CSV_BEGIN")
print(service.dry_run_csv())
print("DRY_RUN_CSV_END")
