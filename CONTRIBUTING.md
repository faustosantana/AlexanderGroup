# Guía de Contribución — Alexander Group (Odoo 19)

Gracias por contribuir. Esta guía define el flujo de trabajo y las convenciones
mínimas del proyecto. Toda la documentación del proyecto está en español.

## Antes de empezar

- Lee el [`README.md`](README.md) y la documentación en [`docs/`](docs/).
- Este proyecto está en **Fase 0** (preparación). No se despliega nada todavía.
- **No** se debe tocar producción de Justech ni el repositorio de Justgroup.

## Requisitos de entorno

- Python 3.10+.
- Herramientas de desarrollo: `pip install -e ".[dev]"` (instala `pytest`,
  `pre-commit`, `black`).
- Instala los hooks: `pre-commit install`.

## Flujo de ramas

Ver [`docs/07_BRANCHING_STRATEGY.md`](docs/07_BRANCHING_STRATEGY.md).

```text
main         # estable, solo por pull request
development  # integración de funcionalidades
feature/*    # una rama por funcionalidad o módulo
fix/*        # correcciones
hotfix/*     # incidentes productivos (futuro)
release/*    # preparación de versiones
```

1. Crea tu rama desde `development`: `feature/<descripcion-corta>`.
2. Realiza cambios pequeños y atómicos.
3. Ejecuta las validaciones locales (ver abajo).
4. Abre un Pull Request hacia `development`.
5. Espera revisión de los responsables (ver [`CODEOWNERS`](CODEOWNERS)).

## Convención de módulos

- Todo desarrollo nuevo usa el prefijo `justech_`.
- Los módulos específicos del proyecto usan `justech_alexander_<nombre_funcional>`.
- Versionado de módulos Odoo: `19.0.x.y.z`.

## Validaciones locales (obligatorias)

```bash
make validate   # validadores de repositorio y de módulos
make test       # pytest
make lint       # black --check
```

o de forma directa:

```bash
python tools/validate_repository.py
python tools/validate_modules.py
pytest
```

## Reglas de seguridad

- Nunca subas secretos, credenciales, certificados, dumps ni filestore.
- Revisa [`SECURITY.md`](SECURITY.md) antes de commitear.

## Mensajes de commit

- Usa mensajes claros en español, en modo imperativo.
- Referencia el issue/tarea cuando aplique.

## Qué NO hacer en esta fase

- No crear módulos Odoo funcionales todavía.
- No copiar código, datos o configuración de Justgroup sin auditoría.
- No inventar información fiscal de las empresas.
