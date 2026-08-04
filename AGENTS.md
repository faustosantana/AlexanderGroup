# AGENTS.md — Alexander Group (Odoo 19)

Guía operativa para agentes. La documentación del proyecto vive en
[`docs/`](docs/) y en [`README.md`](README.md). Aquí solo se registran
aclaraciones **duraderas y no evidentes**.

## Contexto

- **Fase 0**: solo se prepara la base (estructura, documentación, plantillas,
  validadores). **No** hay despliegue de Odoo ni servicios en ejecución.
- No crear módulos Odoo funcionales todavía. Prefijos obligatorios: `justech_`
  y, para este proyecto, `justech_alexander_`.
- Nunca subir secretos, dumps, filestore ni certificados (ver `.gitignore`,
  [`SECURITY.md`](SECURITY.md)).

## Cursor Cloud specific instructions

- **Servicios/aplicaciones de esta fase**: no hay servidor Odoo. La "aplicación"
  ejecutable son las herramientas de calidad: validadores + pruebas + formato.
- **Comandos** (definidos en `Makefile`, `pyproject.toml` y `tools/`):
  - `make validate` → `tools/validate_repository.py` + `tools/validate_modules.py`.
  - `make test` → `pytest` (pruebas de estructura en `tests/`).
  - `make lint` → `black --check .`.
  - `make structure` → imprime el árbol del repositorio.
- **PATH de scripts de consola**: `pip` instala `pytest`, `black` y `pre-commit`
  en `~/.local/bin`. El update script los instala vía `python3 -m pip`. Se añadió
  `~/.local/bin` al `PATH` en `~/.bashrc`, pero si una shell no lo carga, invoca
  con `python3 -m pytest` / `python3 -m black` o usa los objetivos de `make`
  (que ya usan `python3 -m ...` y no dependen del `PATH`).
- **PEP 668**: en esta imagen (Ubuntu, Python 3.12 del sistema) `pip` requiere
  `--break-system-packages` para instalar a nivel de usuario. El update script ya
  lo incluye.
- **Validador de seguridad (no evidente)**: `tools/validate_repository.py`
  ignora a propósito, en el escaneo de secretos, los archivos `*.example`, el
  directorio `tools/` y las líneas con interpolación de variables (`${VAR}`,
  `$(...)`), porque esa es la forma correcta de referenciar credenciales y no un
  secreto literal. Detecta claves de tipo contraseña/token con un valor literal
  real (incluye prefijos, p. ej. una clave `ODOO_DB_PASSWORD` con valor real) e
  ignora placeholders (`CHANGEME`, vacío, `<...>`).
  Retorna `0` si está limpio y `≠0` ante hallazgos; **no borra** archivos.
- **`validate_modules.py`** está preparado para el futuro y hoy retorna `0`
  porque aún no existen módulos (directorios con `__manifest__.py`).
- **Despliegue**: todo lo de `deployment/` son ejemplos (`*.example*`). **No**
  construir imágenes ni levantar contenedores en esta fase.
