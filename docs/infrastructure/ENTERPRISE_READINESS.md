# Odoo 19 Enterprise — Estado de disponibilidad

## Objetivo

Desplegar **Odoo 19 Enterprise** para Doralex / Alexander Group.

## Estado actual: `ENTERPRISE_SOURCE_PENDING=TRUE`

La suscripción/licencia Enterprise está **en trámite**. La arquitectura ya es
**enterprise-ready**: no habrá que rehacerla cuando llegue la licencia.

- `addons_path` **final** desde ya: `/mnt/enterprise,/mnt/custom-addons`.
- El directorio `/opt/doralex/enterprise` **existe desde el inicio** (montado en
  `/mnt/enterprise`, solo lectura), **vacío y protegido** (`chmod 700`) con un
  marcador `ENTERPRISE_SOURCE_PENDING`.
- Imagen actual: `odoo:19` (Community) como base; se cambiará a la imagen/paquetes
  Enterprise cuando exista la fuente legítima. **No** se usan addons Enterprise de
  fuentes no autorizadas ni de repositorios de terceros.

> Regla: cualquier dependencia real de Enterprise se marca
> **`BLOCKED_BY_ENTERPRISE_SOURCE`**; el resto de la infraestructura avanza.

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

## Cuando llegue Enterprise (Fase 28 — sin reconstruir)

1. Colocar/clonar los addons Enterprise en `/opt/doralex/enterprise` desde la
   **fuente legítima**, con la **misma revisión** que Community (ver
   [`../migration/JUSTGROUP_TECHNICAL_REFERENCE.md`](../migration/JUSTGROUP_TECHNICAL_REFERENCE.md)).
2. Ajustar `ODOO_IMAGE` a la imagen Enterprise si corresponde (el `addons_path`
   **no cambia**: ya es `/mnt/enterprise,/mnt/custom-addons`).
3. Actualizar la lista de aplicaciones e instalar los módulos requeridos.
4. Activar la suscripción/base por el procedimiento oficial.
5. Ejecutar pruebas en **Dev** primero.
6. **No** reconstruir el servidor ni recrear las bases de datos.

## Credenciales pendientes

- Suscripción/licencia Odoo Enterprise 19: **PENDIENTE**.
- Acceso a la fuente de addons Enterprise: **PENDIENTE**.
