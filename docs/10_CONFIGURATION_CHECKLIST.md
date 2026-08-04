# 10 — Checklist de Configuración

Lista de verificación para la configuración base de Odoo 19 (Fase 4). Todo queda
**pendiente** hasta el levantamiento e infraestructura.

## Sistema / técnico
- [ ] Versión de Odoo 19 fijada y validada.
- [ ] `odoo.conf` generado desde `config/odoo.conf.example` (sin secretos en Git).
- [ ] `addons_path` correcto (third_party, shared, alexander).
- [ ] `proxy_mode` acorde a Nginx.
- [ ] Workers y límites ajustados al servidor.

## Empresas
- [ ] Alta de las seis compañías (datos oficiales, ver `03_COMPANY_MATRIX.md`).
- [ ] Logos y datos legales.
- [ ] Relaciones intercompañía.

## Contabilidad / fiscal
- [ ] Monedas.
- [ ] Plan de cuentas / matriz contable.
- [ ] Impuestos.
- [ ] Diarios (ventas, compras, banco, caja).
- [ ] Secuencias NCF por empresa.
- [ ] Régimen fiscal por empresa.

## Comercial / logística
- [ ] Bancos y cuentas.
- [ ] Almacenes y ubicaciones.
- [ ] Listas de precios.
- [ ] Productos y categorías.

## Usuarios y seguridad
- [ ] Usuarios definitivos.
- [ ] Grupos y permisos (ver `06_SECURITY_MODEL.md`).
- [ ] Record rules por compañía.
- [ ] Aprobaciones.

## Comunicaciones
- [ ] SMTP saliente (sin credenciales en Git).
- [ ] Plantillas de correo.
- [ ] Plantillas de documentos (factura, cotización, orden).

## Verificación final
- [ ] `python tools/validate_repository.py` sin hallazgos.
- [ ] Pruebas UAT superadas (ver `15_ACCEPTANCE_CRITERIA.md`).
