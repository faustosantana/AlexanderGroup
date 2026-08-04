# tests/

Pruebas del repositorio. En **Fase 0** se valida la **estructura mínima** del
proyecto; las pruebas funcionales de Odoo llegarán con los módulos (Fase 8).

## Ejecutar

```bash
pytest
# o
make test
```

## Contenido

| Archivo             | Propósito                                                  |
| ------------------- | ---------------------------------------------------------- |
| `test_structure.py` | Verifica que exista la estructura mínima requerida.        |

## Notas

- Las pruebas usan solo la biblioteca estándar + `pytest` (sin Odoo).
- No se conectan a servidores ni bases de datos.
