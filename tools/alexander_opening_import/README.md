# Importador de apertura Alexander

Carga **solo** filas pobladas de `Plantilla_PENDIENTES_Alexander_Odoo.xlsx`
y el detalle de los PDFs. No inventa maestros, no consume NCF, no envía
e-CF/correo/DGII.

```text
python3 -m tools.alexander_opening_import.build_payload
python3 -m tools.alexander_opening_import.prepare_named_pdfs
# luego odoo shell + odoo_import.py con OPENING_PAYLOAD_JSON
```

Hojas vacías (usuarios, CxP, activos, bancos pendientes) → 0 registros.
