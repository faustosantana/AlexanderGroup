# Auditoría del servidor — Doralex / Alexander Group

> **ESTADO: PENDING_CREDENTIALS.** Este documento es una **plantilla**. Se completa
> ejecutando `deployment/doralex/scripts/audit_server.sh` (solo lectura) en el
> servidor, una vez que el Cloud Agent tenga acceso por llave.
> **No se ha accedido al servidor.** Nada aquí está inventado.

- Servidor: `2.25.121.111`
- Usuario SSH: `root`
- Regla: **auditar primero, sin instalar nada.** No modificar infraestructura
  antes de terminar la auditoría.

## Conectividad (verificada, sin login)

Desde el Cloud Agent se probó el alcance de red al servidor (una sola vez, sin
autenticar):

- TCP `2.25.121.111:22` **accesible**; handshake SSH completado (host key ED25519).
- Métodos de autenticación ofrecidos: **`publickey,password`**.
- Resultado sin credenciales: `Permission denied (publickey,password)` — esperado.

Conclusión: **la conectividad no es el bloqueo; faltan credenciales.** Para
habilitar el acceso por llave del Cloud Agent, ver "Acceso" abajo.

## Acceso (cómo desbloquear la auditoría)

1. En tu máquina local: `bash deployment/doralex/scripts/setup_ssh_local.sh`
   (crea la llave dedicada, la instala en `root@2.25.121.111` pidiendo la
   contraseña **una sola vez**, y configura los alias SSH).
2. Agrega la **llave privada** (`~/.ssh/doralex_ed25519`) como **Secret** de Cursor
   con nombre `DORALEX_SSH_PRIVATE_KEY` (no se imprime ni se versiona).
3. En el Cloud Agent: `bash deployment/doralex/scripts/cloud_ssh_bootstrap.sh`
   habilita `ssh doralex-server`, y entonces se ejecuta la auditoría.

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
