# Endurecimiento de seguridad — Doralex (servidor)

Lineamientos para el servidor `2.25.121.111`. Se aplican **después** de la
auditoría, sin romper el acceso administrativo.

## Red / exposición

- **PostgreSQL nunca** se publica (sin `ports` en compose). Solo accesible dentro
  de la red Docker de su entorno.
- **Odoo** se publica solo en `127.0.0.1`; el acceso externo pasa por el reverse
  proxy con TLS.
- Firewall (ufw/nftables): permitir solo `22` (SSH), `80` y `443`. Denegar el resto.

```bash
# Ejemplo (ajustar tras auditoría; no ejecutar a ciegas):
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

## SSH

- Preferir **claves** y deshabilitar autenticación por contraseña una vez cargada
  la clave pública del equipo.
- Evaluar `PermitRootLogin prohibit-password` y un usuario administrador con sudo.
- No dejar la contraseña de root en scripts ni en Git.

## Secretos

- Secretos **solo** en `.env` (permisos `600`), fuera de Git.
- `odoo.conf` renderizado (con master password) fuera de Git.
- No imprimir secretos en logs ni en la salida de scripts (los scripts de este
  repo no lo hacen).
- Backups que incluyan `.env`/config se guardan con permisos `600` y, para copia
  offsite, **cifrados**.

## Prohibiciones (nunca en Git)

`.env` reales, `*.pem`/`*.key`/`*.crt`/`*.pfx`/`*.p12`, dumps `*.sql`/`*.dump`,
filestore, backups. Reforzado por `.gitignore` y `tools/validate_repository.py`.

## Verificación

```bash
python tools/validate_repository.py     # 0 = sin secretos/artefactos en el repo
bash deployment/doralex/scripts/validate_isolation.sh   # en el servidor
```
