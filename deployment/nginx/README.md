# deployment/nginx/

Configuración de **ejemplo** de Nginx como proxy inverso para Odoo 19.

| Archivo             | Propósito                                          |
| ------------------- | -------------------------------------------------- |
| `odoo.conf.example` | Server block de referencia (HTTP + WebSocket/TLS). |

## Advertencias

- **No aprobado para producción.**
- Reemplazar `CHANGEME_DOMINIO` por el dominio real (aún no definido).
- Los certificados TLS reales (`*.crt`, `*.key`, `*.pem`) **nunca** se commitean;
  están excluidos por `.gitignore`.
- Habilitar el bloque HTTPS y la redirección 80→443 solo cuando exista
  certificado válido.
- Requiere `proxy_mode = True` en `odoo.conf`.
