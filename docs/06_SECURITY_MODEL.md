# 06 — Modelo de Seguridad

Modelo de seguridad **funcional y técnico** del proyecto. Complementa la política
resumida en [`../SECURITY.md`](../SECURITY.md).

## Separación de empresas

- Aislamiento por compañía mediante `res.company` y **record rules**.
- Cada registro sensible se filtra por `company_id`.
- Definición de qué se comparte y qué se separa: ver
  [`03_COMPANY_MATRIX.md`](03_COMPANY_MATRIX.md).

## Acceso multiempresa

- **Usuarios globales:** acceso controlado a varias compañías (mínimo necesario).
- **Usuarios restringidos por empresa:** acceso a una sola compañía.
- El *company switcher* solo muestra compañías permitidas.

## Roles funcionales (a definir en levantamiento)

| Rol                      | Descripción breve                                  |
| ------------------------ | -------------------------------------------------- |
| Administrador técnico    | Configuración de sistema, addons, infraestructura. |
| Administrador funcional  | Configuración de negocio, no infraestructura.      |
| Administración fiscal    | Impuestos, NCF, cierres fiscales.                  |
| Contabilidad             | Asientos, conciliaciones, reportes contables.      |
| Ventas                   | CRM, cotizaciones, facturación de ventas.          |
| Compras                  | Órdenes de compra, facturas de proveedor.          |
| Inventario               | Almacenes, movimientos, transferencias.            |
| Recursos Humanos         | Empleados, ausencias, (nómina si aplica).          |

## Controles transversales

- **Aprobaciones:** flujos de aprobación por monto/tipo (a definir).
- **Auditoría:** trazabilidad de cambios en registros críticos.
- **Logs:** retención y revisión de logs de acceso y errores.
- **Gestión de credenciales:** fuera de Git, mediante gestor de secretos.
- **Principio de mínimo privilegio:** conceder solo lo estrictamente necesario.

## Prohibiciones (refuerzo)

Nunca en el repositorio:

- Credenciales en código.
- Contraseñas por defecto.
- Tokens en Git.
- Llaves SSH en el repositorio.
- Archivos de respaldo en Git.
- Filestore en Git.
- Dumps SQL en Git.
- Certificados reales en Git.
- Información personal en datos demo.

Estas reglas se validan con `tools/validate_repository.py` y los hooks de
`.pre-commit-config.yaml`.

## Pendientes

- Matriz detallada de grupos y permisos por rol.
- Record rules concretas por modelo.
- Política de rotación de secretos.
