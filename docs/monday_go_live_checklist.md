# Checklist operativo post-deploy — Doralex PROD

`PRODUCTION_DEPLOYED = YES` · `SYSTEM_OPERATIONAL = YES` · `FISCAL_POSTING_READY = NO`

La emisión fiscal sigue bloqueada hasta cargar rangos NCF reales.
El resto del sistema ya está en producción.

## Hoy se puede

- Elegir la empresa del documento (`document.company_id`)
- Cotizar e imprimir V5.3 (DOR PIN DOM MAY REM BLU)
- Enviar cotizaciones (From = `administracion@` del dominio de esa empresa)
- RFQ / OC / recepción / entrega / CRM / maestros
- Crear factura o NC en **borrador** (verá Pendiente de NCF)
- Configurar rangos en el Centro Fiscal cuando lleguen los datos DGII

## Hoy no se puede / no se debe

- Publicar factura o NC fiscal (el motor bloquea si no hay rango válido)
- Inventar NCF `99xxxxxx` ni rangos de ejemplo
- Facturar a clientes reales hasta rangos + revisión humana
- Usar Gmail / `ventas@` / `facturacion@` como From

## Cargar NCF (cuando estén los datos reales)

Por cada empresa y tipo (B01 / B02 / B04 / otros autorizados):

`COMPANY · TYPE · PREFIX · START · END · CURRENT · EXPIRATION · JOURNAL · STATUS`

Activar solo rangos autorizados DGII. No copiar QA de DEV.

## Usuario operacional

Login: `inversionesdoralex@gmail.com`  
Grupos: ventas (todos los documentos), compras, facturación, inventario, multiempresa.  
No es administrador global. Contraseña en el secret store del servidor.

## Cierre visual PROD

`PROD_VISUAL_AUDIT = PASS` · PNG 180 dpi desde PDF reales · sin redesplegar.

Hoy se puede cotizar, comprar, recepcionar, entregar y enviar correo.
Hoy **no** se factura con NCF. Facturas solo en borrador (Pendiente de NCF).

## Checklist para empezar a facturar

1. Cargar rangos NCF reales por empresa
2. Configurar secuencias
3. Configurar vencimientos
4. Validar tipo fiscal por journal
5. Cargar tasa USD si aplica
6. Confirmar términos
7. Revisar banco
8. Hacer primera factura controlada
9. Validar NCF
10. Validar PDF
11. Validar email
12. Registrar primer pago
13. Validar recibo
14. Hacer primera NC controlada

## Si algo falla

1. No forzar NCF a mano.
2. Rollback: `CONFIRM=yes ALLOW_PROD=yes bash /opt/doralex/scripts/restore.sh production production_20260829_104748`
3. Health: `bash /opt/doralex/scripts/healthcheck.sh production`
