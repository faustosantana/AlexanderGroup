# 13 — Registro de Decisiones (ADR)

Bitácora de decisiones de arquitectura y proyecto. Registrar cada decisión
relevante con su contexto y consecuencias.

## Plantilla

```markdown
### ADR-XXX — <título>

- Fecha:
- Estado: Propuesta / Aceptada / Rechazada / Reemplazada
- Contexto:
- Decisión:
- Alternativas consideradas:
- Consecuencias:
- Relacionado con:
```

## Decisiones

### ADR-001 — Repositorio independiente para Alexander Group
- Fecha: Fase 0
- Estado: Aceptada
- Contexto: El proyecto debe ser independiente de los demás proyectos de Justech y
  no reutilizar historial ni archivos Git de Justgroup.
- Decisión: Crear un repositorio propio (`faustosantana/AlexanderGroup`) sin
  submódulos y sin importar Git de Justgroup.
- Alternativas consideradas: Monorepo con Justgroup (descartado por acoplamiento y
  riesgo de mezcla).
- Consecuencias: Aislamiento claro; la reutilización de módulos se hace por
  auditoría explícita, no por dependencia de repositorio.
- Relacionado con: R01, [`07_BRANCHING_STRATEGY.md`](07_BRANCHING_STRATEGY.md).

### ADR-002 — Convención de prefijos de módulos
- Fecha: Fase 0
- Estado: Aceptada
- Contexto: Necesidad de trazabilidad y evitar colisiones de nombres.
- Decisión: Prefijo `justech_` para desarrollo nuevo y `justech_alexander_` para
  módulos específicos del grupo.
- Consecuencias: Nombres consistentes y filtrables.
- Relacionado con: `addons/alexander/README.md`.

### Decisiones abiertas (pendientes)
- Community vs. Enterprise.
- Una instancia multiempresa vs. instancias separadas.
- Estrategia de facturación electrónica / NCF.
- Estrategia de consolidación contable.
