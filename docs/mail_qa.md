# Mail QA

Gate A (corridas anteriores): MX/SPF/DKIM/DMARC 6/6, Graph PASS, From alias PASS, incoming PASS, CRM inbound PASS.

## Revalidación esta corrida

| Check | Estado |
| --- | --- |
| `company.email` = `administracion@dominio` 6/6 | PASS |
| PDF usa `document.company_id` | PASS |
| Wizard Enviar y imprimir (UI) | NOT_TESTED |
| Envío real a buzón interno | NOT_TESTED (no se disparó cola para no inundar) |
| Subject / filename | Configurado en acciones: `Cotizacion_`, `Factura_`, `Nota_Credito_`, `Recibo_`, `Orden_Compra_` |

## Reply-To

Sigue la identidad de la compañía del documento. Threading técnico de Odoo no se alteró.

## Pendiente lunes

Primera cotización y primera factura: verificar From + PDF adjunto en el buzón `administracion@` de esa empresa, no en Gmail personal.
