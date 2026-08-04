# addons/shared

Módulos **reutilizables** provenientes del ecosistema Justech (Justgroup), que se
incorporarán a este proyecto **únicamente después de ser auditados y aprobados**
mediante el proceso definido en [`docs/05_REUSE_ASSESSMENT.md`](../../docs/05_REUSE_ASSESSMENT.md).

## Propósito

Contendrá componentes comunes y reutilizables como, por ejemplo:

- Localización dominicana.
- Comprobantes Fiscales (NCF).
- Diseños de reportes.
- Utilidades generales.
- Integraciones reutilizables.

## Reglas

- **Nada debe copiarse todavía.** Esta carpeta permanece vacía (solo este README)
  hasta que exista un levantamiento y una auditoría formal de cada módulo.
- Todo módulo que llegue aquí debe:
  - Haber pasado la evaluación de reutilización (clasificación Verde o Azul).
  - No contener referencias fijas a empresas de Justech u otros clientes.
  - No contener credenciales, tokens ni datos productivos.
  - Ser compatible con **Odoo 19**.
- Convención de nombres: prefijo `justech_` para todo desarrollo nuevo/común.
- No se debe modificar producción de Justech ni el repositorio de Justgroup para
  obtener estos módulos.

## Estado

`Fase 0 — Vacío por diseño. Pendiente de auditoría y aprobación.`
