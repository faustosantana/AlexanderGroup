# Alexander Group — Odoo 19 Multiempresa

**Estado:** `Fase 0 — Preparación del repositorio y arquitectura`

> ⚠️ **Advertencia:** Todavía **no** existe ningún ambiente desplegado. Este
> repositorio contiene únicamente la base técnica (estructura, documentación,
> convenciones y plantillas). No hay servidores, dominios, credenciales, bases de
> datos ni contenedores en ejecución.

## Descripción

Repositorio oficial e **independiente** para la implementación de **Odoo 19**
destinada al grupo empresarial de Alexander Piña (**Alexander Group**), compuesto
por **seis empresas** relacionadas. El proyecto es propiedad de **Justech SRL**.

## Objetivo

Preparar una base profesional, limpia, documentada y segura que permita
posteriormente implementar Odoo 19 multiempresa, reutilizando —tras auditoría—
los módulos y personalizaciones reutilizables del entorno Justgroup de Justech.

## Estado actual

- Fase 0 completada a nivel de **estructura y documentación**.
- Sin código funcional de Odoo.
- Sin datos productivos, credenciales ni despliegues.

## Alcance inicial (lo que SÍ se prepara ahora)

- Repositorio y arquitectura de carpetas.
- Documentación inicial (en español).
- Convenciones de nombres y de contribución.
- Plantillas de configuración (`*.example`).
- Inventarios y matrices vacías, listas para completar.
- Estrategia Git.
- Base técnica para futuras personalizaciones.
- Validadores de seguridad y estructura.

## Exclusiones actuales (lo que NO se hace ahora)

- No se despliega ni instala Odoo.
- No se copian bases de datos, filestore, credenciales, `.env` ni certificados.
- No se toca producción de Justech ni el repositorio de Justgroup.
- No se crean módulos Odoo funcionales.
- No se asume ni inventa información fiscal de las empresas.
- No se realizan conexiones a servidores.

## Arquitectura de alto nivel

- **Odoo 19** (Community/Enterprise por confirmar) sobre **PostgreSQL**.
- Despliegue previsto vía contenedores (Docker) con proxy inverso (Nginx).
- Modelo **multiempresa** para seis compañías, con procesos compartidos y
  separados, e **intercompañía** (ventas, compras, transferencias, consolidación).
- Detalle en [`docs/01_ARCHITECTURE.md`](docs/01_ARCHITECTURE.md).

## Estructura del repositorio

```text
AlexanderGroup/
├── addons/            # shared / alexander / third_party (módulos)
├── config/            # plantillas de configuración (*.example)
├── deployment/        # docker, nginx, scripts (solo ejemplos)
├── docs/              # documentación 00–15 (español)
├── migrations/        # notas y scripts de migración (futuro)
├── tests/             # pruebas (estructura del repo)
├── tools/             # validadores (repositorio y módulos)
└── (archivos raíz)    # Makefile, pyproject.toml, políticas, etc.
```

## Requisitos futuros (pendientes)

Servidor definitivo, IPs, dominios, credenciales, bases de datos, información
fiscal de las seis empresas, usuarios definitivos, procesos internos, matriz
contable, configuración de correo, certificados y datos productivos.

## Convención de módulos

- Prefijo general para desarrollo nuevo: `justech_`.
- Prefijo específico del proyecto: `justech_alexander_<nombre_funcional>`.
- Versionado de módulos Odoo: `19.0.x.y.z`.

## Estrategia de ramas

`main`, `development`, `feature/*`, `fix/*`, `hotfix/*`, `release/*`.
Detalle en [`docs/07_BRANCHING_STRATEGY.md`](docs/07_BRANCHING_STRATEGY.md).

## Reglas de seguridad

Ningún secreto en Git. Ver [`SECURITY.md`](SECURITY.md) y
[`docs/06_SECURITY_MODEL.md`](docs/06_SECURITY_MODEL.md).

## Flujo de contribución

Ver [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Comandos rápidos

```bash
make help            # ayuda
make validate        # validadores de repositorio y módulos
make test            # pytest
make lint            # black --check
make structure       # muestra la estructura del repositorio
```

## Próximos pasos

1. **Fase 1 — Levantamiento**: completar la matriz de empresas
   ([`docs/03_COMPANY_MATRIX.md`](docs/03_COMPANY_MATRIX.md)) y el cuestionario
   ([`docs/11_DISCOVERY_QUESTIONNAIRE.md`](docs/11_DISCOVERY_QUESTIONNAIRE.md)).
2. **Fase 2 — Auditoría Justgroup**: completar el inventario
   ([`docs/04_MODULE_INVENTORY.md`](docs/04_MODULE_INVENTORY.md)) y la evaluación
   de reutilización ([`docs/05_REUSE_ASSESSMENT.md`](docs/05_REUSE_ASSESSMENT.md)).
3. Ver el plan completo en
   [`docs/02_IMPLEMENTATION_PLAN.md`](docs/02_IMPLEMENTATION_PLAN.md).
