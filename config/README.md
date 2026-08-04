# config/

Plantillas de configuración del proyecto. **Ningún archivo aquí contiene valores
reales ni secretos.** Los archivos productivos se generan a partir de estas
plantillas y quedan excluidos por `.gitignore`.

## Archivos

| Archivo             | Propósito                                                        |
| ------------------- | ---------------------------------------------------------------- |
| `env.example`       | Variables de entorno de ejemplo. Copiar a `.env` (ignorado).     |
| `odoo.conf.example` | Configuración de Odoo 19 de ejemplo. Copiar a `odoo.conf` (ignorado). |

## Uso

```bash
cp config/env.example .env
cp config/odoo.conf.example config/odoo.conf   # o donde lo monte el contenedor
```

Luego completar los valores. **Nunca** commitear `.env` ni `odoo.conf` reales.

## Reglas

- Los valores sensibles se dejan vacíos o como `CHANGEME_*`.
- Los secretos de producción se gestionan fuera de Git (gestor de secretos del
  servidor, por definir).
- Validar antes de commitear: `python tools/validate_repository.py`.
