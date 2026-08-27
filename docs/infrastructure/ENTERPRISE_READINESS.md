# Odoo 19 Enterprise — Estado de disponibilidad

## Objetivo

Desplegar **Odoo 19 Enterprise** para Doralex / Alexander Group.

## Estado actual: `BLOCKED`

La imagen pública `odoo:19` es **Community**. Enterprise requiere los addons
Enterprise, que **no** son públicos y exigen una **licencia/suscripción** y acceso
legítimo a su fuente. **No se inventa acceso Enterprise.**

Mientras no se confirme la fuente legítima, el stack se define con imagen
Community como placeholder (`ODOO_IMAGE=odoo:19`) y un punto de montaje preparado
para los addons Enterprise (`/mnt/enterprise`, comentado).

## Se debe confirmar antes de instalar Enterprise

- [ ] Versión exacta (p. ej. `19.0` + fecha/build).
- [ ] Fuente legítima de Enterprise disponible (suscripción Odoo / repo `enterprise`
      con acceso autorizado / imagen oficial Enterprise).
- [ ] Dependencias del sistema y de Python.
- [ ] Imagen o paquetes a usar (y cómo se construyen).
- [ ] Método de actualización/parcheo.
- [ ] Términos de licencia y número de usuarios contratados.

## Si falta credencial / repo / licencia

**Detenerse y reportar** (como aquí). No descargar ni empaquetar Enterprise sin
autorización.

## Cómo se habilitará (cuando haya acceso)

1. Obtener los addons Enterprise por el medio autorizado.
2. Construir una imagen que los incluya **o** montarlos en `/mnt/enterprise`.
3. Ajustar `ODOO_IMAGE` y `addons_path` (`/mnt/enterprise,/mnt/extra-addons`).
4. Validar arranque en **Dev** antes que en Produccion.

## Credenciales pendientes

- Suscripción/licencia Odoo Enterprise 19: **PENDIENTE**.
- Acceso a la fuente de addons Enterprise: **PENDIENTE**.
