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

## Si algo falla

1. No forzar NCF a mano.
2. Rollback: `CONFIRM=yes ALLOW_PROD=yes bash /opt/doralex/scripts/restore.sh production production_20260829_104748`
3. Health: `bash /opt/doralex/scripts/healthcheck.sh production`
