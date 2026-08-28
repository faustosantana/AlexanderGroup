# Go-live checklist — Doralex (DEV preparado, PROD no desplegado)

Fecha: 2026-08-28. Solo DEV. `PRODUCTION_DEPLOYED = NO`. `PROD_UNTOUCHED = YES`.

## Gates

| Gate | Tema | Estado |
| --- | --- | --- |
| A | Mail Microsoft 365 / From `administracion@` / `document.company_id` | PASS (revalidado: email 6/6). Envío UI nativo esta corrida: NOT_TESTED |
| B | Reportes V2.3 | FUNCTIONAL PASS · VISUAL PENDING (aprobación humana) |
| C | Fiscal NCF QA | PASS en DEV con rangos `99xxxxxx`. Rangos DGII reales: NO cargados |
| D | Contabilidad (asientos, pagos, NC, estado) | PASS en flujos QA. USD: NOT_TESTED (sin tasa) |
| E | Multiempresa / NCF cruzado | PASS (Blue Elite activo + factura Rempart = NCF Rempart) |
| F | Permisos lunes | BLOCKED — el usuario operativo no tiene grupos fiscales / Recuperación Contable |
| G | Backups | DEV backup `dev_20260828_180739`. Restore no ejecutado (destructivo) |

## Antes de facturar en producción (humano)

1. Backup PROD verificado.
2. Cargar **rangos NCF reales autorizados** (no reutilizar banda QA `99xxxxxx`).
3. Confirmar `next_sequence` inicial y vencimiento DGII por empresa.
4. Asignar grupos: facturación, NC fiscal, Recuperación Contable (solo a quien corresponda).
5. Confirmar términos comerciales y datos bancarios definitivos.
6. Primera factura / NC / pago / correo: verificación humana del NCF, From y PDF.
7. Deploy de módulos **solo con autorización**. Este PR no se aplica a PROD.

## Nunca

- Reutilizar un NCF emitido.
- “Resetear” una secuencia DGII real.
- Facturar en PROD desde este agente.
- Confundir NCF QA (`B0199…`) con NCF de producción.
