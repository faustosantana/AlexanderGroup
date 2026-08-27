# tools/

Utilidades de validación del repositorio. Usan solo la **biblioteca estándar** de
Python (sin dependencias externas) y **no** modifican ni borran archivos.

| Script                   | Propósito                                                        | Código de salida |
| ------------------------ | ---------------------------------------------------------------- | ---------------- |
| `validate_repository.py` | Verifica seguridad y estructura mínima del repositorio.          | `0` OK / `≠0` riesgos |
| `validate_modules.py`    | Valida módulos Odoo (preparado; funciona aunque no existan aún). | `0` OK / `≠0` errores |
| `scan_module_hygiene.py` | Escanea módulos custom en busca de hardcodes (company_id fijo, refs Justech, emails/URLs/RNC). | `0` OK / `≠0` hallazgos |

## Uso

```bash
python tools/validate_repository.py
python tools/validate_modules.py
# o
make validate
```

## Notas

- `validate_repository.py` **no borra** nada automáticamente; solo reporta.
- `validate_modules.py` está preparado para revisar módulos futuros y hoy termina
  correctamente porque aún no existen módulos funcionales.
