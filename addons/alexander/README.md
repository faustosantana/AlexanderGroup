# addons/alexander

Módulos **específicos** Doralex / Alexander Group. Prefijo obligatorio:

```text
justech_alexander_<nombre_funcional>
```

## Módulos

| Módulo | Propósito |
| ------ | --------- |
| `justech_alexander_base` | Códigos de empresa, ficha pública, nomenclatura de almacenes/diarios/secuencias |
| `justech_alexander_website` | Website institucional público (sin datos confidenciales) |
| `justech_alexander_admin` | Centro Administración Doralex (reutiliza la clave administrativa Justech) |
| `justech_alexander_reports` | Layout A4 central, identidad por `company_id` y vista previa |
| `justech_alexander_microsoft_mail` | Microsoft Graph: user mailbox `administracion@` + aliases por empresa |

## Reglas

- No editar `addons/vendor/odoo-custom-addons/` (regenerable).
- No incluir credenciales, RNC de más, cuentas bancarias ni cédulas en Git.
- El website solo muestra nombre comercial, logo, sector y descripción pública.
- Compatible con **Odoo 19** (`version: 19.0.x.y.z`).
