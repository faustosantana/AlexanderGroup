# Política de Seguridad — Alexander Group

Este documento resume las reglas de seguridad **obligatorias** del repositorio.
El modelo de seguridad funcional/técnico detallado está en
[`docs/06_SECURITY_MODEL.md`](docs/06_SECURITY_MODEL.md).

## Principios

- Principio de **mínimo privilegio** en todos los accesos.
- Separación estricta entre empresas (multiempresa).
- Ningún secreto vive en el control de versiones.

## Prohibiciones (nunca en Git)

- Credenciales en código.
- Contraseñas por defecto.
- Tokens en Git.
- Llaves SSH en el repositorio.
- Archivos de respaldo (`*.backup`, `*.zip`, `*.tar.gz`) en Git.
- Filestore de Odoo en Git.
- Dumps SQL (`*.sql`, `*.dump`) en Git.
- Certificados reales (`*.pem`, `*.key`, `*.crt`, `*.pfx`, `*.p12`) en Git.
- Información personal real en datos demo.

Estas prohibiciones se refuerzan mediante `.gitignore`,
`tools/validate_repository.py` y los hooks de `.pre-commit-config.yaml`.

## Manejo de secretos

- Usar variables de entorno a partir de `config/env.example` (sin valores reales).
- Las credenciales de producción se gestionarán fuera de Git (gestor de secretos
  del servidor, aún no definido).

## Reporte de vulnerabilidades

Ante una posible vulnerabilidad o exposición de secretos:

1. **No** abrir un issue público con detalles sensibles.
2. Contactar de forma privada al responsable del repositorio (`@faustosantana`).
3. Si se detecta un secreto ya commiteado, rotarlo de inmediato y purgarlo del
   historial.

## Validación

Antes de cada commit se recomienda ejecutar:

```bash
python tools/validate_repository.py
```

El comando retorna un código distinto de `0` si detecta riesgos de seguridad.
