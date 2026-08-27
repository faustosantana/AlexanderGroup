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

## Infraestructura Doralex (servidor nuevo)

- El bootstrap de infraestructura vive en `deployment/doralex/` (stacks Prod/Dev
  aislados) y `docs/infrastructure/`. Es **fuente de verdad versionada**; se
  despliega en el servidor bajo `/opt/doralex/**` (aún no desplegado).
- **STOP por SSH (no evidente y obligatorio)**: el servidor `2.25.121.111`
  (user `root`) **no** debe accederse por SSH hasta que el usuario lo autorice y
  entregue la contraseña. Cuando una tarea requiera SSH, DETENERSE y responder
  solo con el bloque `SSH_REQUIRED` (host/user/reason) y esperar. Nunca simular
  acceso ni inventar resultados de auditoría.
- **Aislamiento Prod/Dev**: redes (`doralex_prod_net` / `doralex_dev_net`),
  volúmenes (`doralex_prod_*` / `doralex_dev_*`), DB y puertos loopback distintos
  (Prod `8069/8072`, Dev `8169/8172`). PostgreSQL nunca se publica. Nunca montar
  volúmenes de Produccion en Dev. `scripts/validate_isolation.sh` lo verifica.
- **Secretos de infra**: cada entorno usa su `.env` (desde `.env.example`) y un
  `config/odoo.conf` **renderizado** con `scripts/render_config.sh` (envsubst);
  ambos quedan fuera de Git. Enterprise (`/opt/doralex/*/enterprise`) también.
- **Validación local sin Docker**: los scripts se comprueban con `shellcheck -x`
  y `bash -n`; los compose con `yamllint`/`pyyaml`; Docker **no** está instalado
  en el entorno de Cursor (el despliegue real ocurre en el servidor).
- **Enterprise**: `odoo:19` es Community; Enterprise está **BLOCKED** hasta contar
  con licencia/fuente legítima (ver `docs/infrastructure/ENTERPRISE_READINESS.md`).
