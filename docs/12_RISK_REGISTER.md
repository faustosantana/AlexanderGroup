# 12 — Registro de Riesgos

Escalas sugeridas: **Probabilidad** e **Impacto** en {Bajo, Medio, Alto}.
**Severidad** = combinación de ambos. Actualizar el estado a medida que avanza el
proyecto.

| ID | Riesgo | Probabilidad | Impacto | Severidad | Mitigación | Responsable | Estado |
| -- | ------ | ------------ | ------- | --------- | ---------- | ----------- | ------ |
| R01 | Mezcla accidental con repositorios de Justech | Media | Alto | Alta | Repositorio independiente; sin submódulos; validador de repositorio; revisión en PR | @faustosantana | Abierto |
| R02 | Copia de credenciales | Media | Alto | Alta | `.gitignore`, `detect-private-key`, `validate_repository.py`, revisión | @faustosantana | Abierto |
| R03 | Dependencias ocultas de módulos | Alta | Medio | Alta | Inventario y auditoría de dependencias (Fase 2) | @faustosantana | Abierto |
| R04 | Código con referencias a compañías de Justech | Alta | Medio | Alta | Evaluación de reutilización; búsqueda de IDs/hardcodeos | @faustosantana | Abierto |
| R05 | Reglas multiempresa incorrectas | Media | Alto | Alta | Diseño de record rules; pruebas de aislamiento | @faustosantana | Abierto |
| R06 | Configuración fiscal incompleta | Media | Alto | Alta | Levantamiento fiscal; checklist de configuración | @faustosantana | Abierto |
| R07 | Falta de levantamiento | Media | Alto | Alta | Cuestionario de levantamiento (Fase 1) | @faustosantana | Abierto |
| R08 | Migración de datos deficiente | Media | Alto | Alta | Plan de migración; validaciones; pruebas | @faustosantana | Abierto |
| R09 | Ausencia de backups | Baja | Alto | Media | Estrategia de backups y pruebas de restauración | @faustosantana | Abierto |
| R10 | Cambios directos en producción | Media | Alto | Alta | Flujo por PR; ramas protegidas; sin acceso directo | @faustosantana | Abierto |
| R11 | Dependencia excesiva de módulos personalizados | Media | Medio | Media | Preferir estándar; documentar personalizaciones | @faustosantana | Abierto |
| R12 | Falta de pruebas UAT | Media | Alto | Alta | Plan de pruebas y criterios de aceptación | @faustosantana | Abierto |
| R13 | Accesos cruzados entre empresas | Media | Alto | Alta | Record rules; pruebas de seguridad multiempresa | @faustosantana | Abierto |
| R14 | Falta de responsable funcional | Media | Medio | Media | Asignar responsable por área/empresa | @faustosantana | Abierto |
| R15 | Requerimientos no documentados | Alta | Medio | Alta | Cuestionario; registro de decisiones | @faustosantana | Abierto |

## Notas

- Este registro es inicial; ampliar conforme se identifiquen nuevos riesgos.
- Los responsables definitivos se asignarán durante el levantamiento.
