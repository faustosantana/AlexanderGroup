# Auditoría del servidor — Doralex / Alexander Group

> **ESTADO: PENDING_SSH.** Este documento es una **plantilla**. Se completa
> ejecutando `deployment/doralex/scripts/audit_server.sh` (solo lectura) en el
> servidor, una vez autorizada la conexión SSH y entregada la contraseña.
> **No se ha accedido al servidor.** Nada aquí está inventado.

- Servidor: `2.25.121.111`
- Usuario SSH: `root`
- Regla: **auditar primero, sin instalar nada.** No modificar infraestructura
  antes de terminar la auditoría.

## Cómo generar este informe

```bash
# En el servidor (tras autorizar SSH):
bash /opt/doralex/scripts/audit_server.sh > SERVER_AUDIT_$(date +%Y%m%d_%H%M%S).md
# Pegar el resultado bajo "Resultados" y commitear (sin secretos).
```

## Ítems a auditar (checklist)

- [ ] hostname
- [ ] OS y versión
- [ ] CPU
- [ ] RAM
- [ ] disco
- [ ] mounts
- [ ] swap
- [ ] red
- [ ] puertos abiertos
- [ ] firewall
- [ ] servicios activos
- [ ] Docker instalado (sí/no)
- [ ] Docker Compose (sí/no)
- [ ] PostgreSQL existente (sí/no)
- [ ] Nginx/Traefik existente (sí/no)
- [ ] certificados existentes
- [ ] usuarios
- [ ] timezone
- [ ] locale
- [ ] SSH config
- [ ] espacio disponible
- [ ] backups / snapshot del proveedor (si aplica)

## Resultados

_Pendiente de ejecución (PENDING_SSH)._

## Hallazgos y decisiones

_Pendiente._ Registrar conflictos de puertos, software preexistente, riesgos de
seguridad y decisiones derivadas (p. ej. reutilizar o no un PostgreSQL/Nginx ya
instalado).
