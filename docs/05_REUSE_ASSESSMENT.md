# 05 — Evaluación de Reutilización

Proceso **formal** para evaluar cada módulo existente de Justgroup antes de
reutilizarlo. Ningún módulo se copia sin superar esta evaluación.

## Criterios de revisión (checklist por módulo)

Para cada módulo se revisa:

- [ ] Funcionalidad.
- [ ] Dependencias.
- [ ] Datos hardcodeados.
- [ ] Referencias a Justech.
- [ ] Referencias a compañías específicas.
- [ ] IDs fijos.
- [ ] Configuración fiscal.
- [ ] Seguridad.
- [ ] Reglas multiempresa.
- [ ] Record rules.
- [ ] Grupos.
- [ ] Secuencias.
- [ ] Plantillas QWeb.
- [ ] Correos.
- [ ] URLs.
- [ ] APIs.
- [ ] Credenciales.
- [ ] Cron jobs.
- [ ] Automatizaciones.
- [ ] Dependencias Enterprise.
- [ ] Compatibilidad con Odoo 19.
- [ ] Cobertura de pruebas.
- [ ] Licenciamiento.
- [ ] Riesgos.

## Clasificación final

| Color   | Significado                          | Acción                                   |
| ------- | ------------------------------------ | ---------------------------------------- |
| 🟢 Verde | Reutilizable sin cambios             | Mover a `addons/shared` tras aprobar.    |
| 🟡 Amarillo | Reutilizable con adaptación       | Adaptar (prefijo `justech_`) y probar.   |
| 🔴 Rojo | No reutilizable                      | Reescribir o sustituir.                  |
| 🔵 Azul | Debe convertirse en módulo común     | Refactorizar como módulo `justech_*`.    |

## Ficha de evaluación (plantilla)

Copiar este bloque por cada módulo evaluado:

```markdown
### Módulo: <nombre_tecnico>

- Repositorio origen:
- Versión:
- Tipo:
- Resumen de funcionalidad:
- Hallazgos (referencias/IDs/credenciales/hardcodeos):
- Dependencias (incluye Enterprise):
- Compatibilidad Odoo 19:
- Riesgos:
- Clasificación: 🟢 / 🟡 / 🔴 / 🔵
- Decisión (ver 04_MODULE_INVENTORY):
- Responsable:
- Fecha:
```

## Registro de evaluaciones

_Pendiente._ Aún no se ha evaluado ningún módulo (Fase 2).
