# 00 — Visión General del Proyecto

**Proyecto:** Alexander Group — Odoo 19 Multiempresa
**Titular:** Justech SRL
**Estado:** `Fase 0 — Preparación del repositorio y arquitectura`

## Propósito

Implementar **Odoo 19** para el grupo empresarial de **Alexander Piña**, compuesto
por **seis empresas** relacionadas, reutilizando —tras auditoría— los módulos y
personalizaciones reutilizables del entorno Justgroup de Justech.

## Alcance de esta fase (Fase 0)

Se prepara **exclusivamente** la base técnica:

- Repositorio independiente y arquitectura de carpetas.
- Documentación inicial en español.
- Convenciones de nombres y contribución.
- Plantillas de configuración (`*.example`).
- Inventarios y matrices vacías.
- Estrategia Git.
- Validadores de seguridad y estructura.

## Fuera de alcance ahora

Servidor, IPs, dominios, credenciales, bases de datos, información fiscal de las
empresas, usuarios definitivos, procesos internos, matriz contable, correo,
certificados y datos productivos. **No** se despliega ni instala Odoo.

## Restricciones clave

- No tocar producción de Justech.
- No modificar el repositorio de Justgroup.
- No copiar bases de datos, filestore, credenciales, `.env` ni certificados.
- No crear módulos Odoo funcionales todavía.
- Prefijos obligatorios: `justech_` y, para este proyecto, `justech_alexander_`.
- No hacer commit ni push hasta presentar el resultado para revisión.

## Documentos relacionados

- Arquitectura: [`01_ARCHITECTURE.md`](01_ARCHITECTURE.md)
- Plan de implementación: [`02_IMPLEMENTATION_PLAN.md`](02_IMPLEMENTATION_PLAN.md)
- Matriz de empresas: [`03_COMPANY_MATRIX.md`](03_COMPANY_MATRIX.md)
- Criterios de aceptación: [`15_ACCEPTANCE_CRITERIA.md`](15_ACCEPTANCE_CRITERIA.md)
