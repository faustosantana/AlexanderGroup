# 07 — Estrategia de Ramas

## Ramas

```text
main
development
feature/*
fix/*
hotfix/*
release/*
```

## Reglas por rama

### `main`
- Código **estable**, preparado para producción.
- Solo recibe cambios mediante **pull request**.
- **No** se desarrolla directamente sobre `main`.

### `development`
- Rama de **integración** de funcionalidades.
- Base para pruebas.
- Recibe ramas `feature/*` y `fix/*`.

### `feature/*`
- Una rama por funcionalidad o módulo.
- Ejemplos:

```text
feature/repository-baseline
feature/company-configuration
feature/justech-l10n-do-base
feature/alexander-security
```

### `fix/*`
- Correcciones no urgentes integradas vía `development`.

### `hotfix/*`
- Solo para **incidentes productivos futuros**.

### `release/*`
- Preparación de versiones antes de promover a `main`.

## Flujo resumido

```text
feature/* ─┐
fix/*     ─┼─▶ development ─▶ release/* ─▶ main
hotfix/*  ─────────────────────────────▶ main (y back-merge a development)
```

## Versionado

- Versionado compatible con módulos Odoo: `19.0.x.y.z`.
- **No crear tags todavía.**

## Convenciones

- Nombres de rama en minúsculas, kebab-case.
- Pull requests con revisión de los responsables (ver [`../CODEOWNERS`](../CODEOWNERS)).
- Sin submódulos Git por ahora.
