# 15 — Criterios de Aceptación

## Fase 0 — Preparación del repositorio

La fase se considera completada **únicamente** si:

1. [ ] La estructura completa fue creada.
2. [ ] No existen credenciales.
3. [ ] No existe código copiado de Justgroup.
4. [ ] No se crearon módulos Odoo funcionales.
5. [ ] Todos los documentos están en español.
6. [ ] Los scripts ejecutan sin errores.
7. [ ] Las pruebas pasan.
8. [ ] El repositorio valida correctamente.
9. [ ] No se hizo deployment.
10. [ ] No se realizó push (hasta aprobación).
11. [ ] No se hicieron cambios en otros repositorios.
12. [ ] No se tocaron servidores.
13. [ ] Se presenta un resumen completo antes de realizar commits.

## Verificación técnica

```bash
python tools/validate_repository.py   # código 0 = sin hallazgos
python tools/validate_modules.py      # código 0 = OK (sin módulos aún)
pytest                                # estructura mínima presente
```

## Criterios para fases futuras

Cada fase posterior (1–10) definirá sus propios criterios de aceptación y UAT,
enlazados desde el [`02_IMPLEMENTATION_PLAN.md`](02_IMPLEMENTATION_PLAN.md). Los
criterios funcionales, fiscales y de seguridad multiempresa se detallarán tras el
levantamiento.
