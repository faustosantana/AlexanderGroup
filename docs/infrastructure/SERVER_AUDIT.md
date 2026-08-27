# Auditoría del servidor — Doralex / Alexander Group

> **ESTADO: COMPLETADA (solo lectura) — 2026-08-27.** Ejecutada con
> `deployment/doralex/scripts/audit_server.sh` vía `ssh doralex-server`.
> **No se modificó nada.** Resultados curados (sin secretos).

- Servidor: `2.25.121.111`
- Acceso: por **llave SSH** (root y `doralexadmin` con sudo NOPASSWD). PASS.

## ⚠️ Hallazgo crítico: existe una instalación previa

El servidor **NO está limpio**. Hay un stack Odoo en ejecución (Docker):

| Contenedor | Imagen | Estado | Puertos |
| ---------- | ------ | ------ | ------- |
| `odoo-aeju-odoo-1` | **`odoo:18`** | Up ~51 min | `0.0.0.0:32768->8069`, `8071-8072` |
| `odoo-aeju-db-1` | `postgres:17-alpine` | Up (healthy) | `5432/tcp` (interno) |
| `traefik-traefik-1` | `traefik:latest` | Up ~51 min | escucha host `:80` y `:443` |

- Volúmenes: `odoo-aeju_db`, `odoo-aeju_odoo-addons`, `odoo-aeju_odoo-data`,
  `traefik-letsencrypt`, `traefik_traefik-letsencrypt`.
- Red: `odoo-aeju_default`. Reverse proxy actual: **Traefik** (no Nginx).
- **Odoo 18**, no 19. Parece una instalación previa (posible plantilla del
  proveedor / prueba). **No se toca** hasta tu decisión.

> Regla aplicada: "comprobar que no existe una instalación previa que podamos
> destruir" → **existe**. Me detengo antes de instalar/desplegar nada.

## Recursos

| Recurso | Valor |
| ------- | ----- |
| Hostname | `Doralexgroup` |
| OS | Ubuntu 24.04.4 LTS |
| Kernel | 6.8.0-138-generic (x86_64, KVM/QEMU) |
| CPU | 2 vCPU — AMD EPYC 9354P |
| RAM | 7.8 GiB (≈7.2 GiB disponible) |
| Swap | **0 B** (no configurado) |
| Disco | `/dev/sda1` ext4 96 GB (4.6 GB usado, **92 GB libres**) |
| Timezone | **`Etc/UTC`** (se requiere `America/Santo_Domingo`, Fase 6) |
| Locale | `C.UTF-8` / `en_US.UTF-8` |
| NTP | activo (reloj sincronizado) |

## Software presente

| Componente | Estado |
| ---------- | ------ |
| Docker | **29.7.2** (instalado) |
| Docker Compose | **v5.5.0** (plugin) |
| PostgreSQL host | no (va en contenedor) |
| Nginx host | no |
| Traefik | **sí (contenedor)**, ocupa `:80` y `:443` |
| ufw | **inactivo** |
| fail2ban | no detectado |

## Red / puertos en escucha (host)

| Puerto | Servicio | Exposición |
| ------ | -------- | ---------- |
| `22/tcp` | sshd | pública |
| `80/tcp` | traefik | pública |
| `443/tcp` | traefik | pública |
| `32768/tcp` | docker-proxy → odoo `8069` | **pública (0.0.0.0)** |
| `53` | systemd-resolved | loopback |

- IP: `2.25.121.111/24` (eth0) + IPv6 `2a02:4780:95:ec6::1/48`.
- Firewall de host: **ufw inactivo**; solo reglas de Docker (nft/iptables).
  `5432` no está publicado al exterior (bien).

## SSH (config efectiva)

`Port 22`, `PermitRootLogin yes`, `PasswordAuthentication yes`,
`PubkeyAuthentication yes`. Pendiente de hardening (tras confirmar acceso por
llave varias veces).

## Seguridad — observaciones

- Un Odoo 18 previo queda **expuesto públicamente** en `:32768`.
- `PasswordAuthentication yes` y `PermitRootLogin yes` (endurecer luego).
- `ufw` inactivo (definir 22/80/443 y cerrar el resto).
- Se detectó un **hash** de contraseña root en la config de cloud-init durante la
  auditoría; **no** se versiona (se removió del volcado del script por privacidad).

## Decisión requerida (antes de continuar)

El plan Doralex usa Nginx en `:80/:443` y Odoo en `127.0.0.1:8069/8169`. Hay un
conflicto directo: **Traefik ya ocupa `:80/:443`** y existe el stack `odoo-aeju`
(Odoo 18). Opciones:

1. **Retirar** el stack previo (`odoo-aeju` + su Traefik) si es desechable, y
   desplegar Doralex limpio (Nginx + Odoo 19). — requiere tu confirmación explícita.
2. **Conservarlo** e integrar Doralex detrás del **Traefik existente** (adaptar la
   arquitectura de reverse proxy a Traefik en vez de Nginx).
3. **Coexistir** temporalmente en puertos alternos hasta migrar.

`REQUIRED`: indicar qué hacer con `odoo-aeju`/Traefik antes de instalar o desplegar.
No se modificará nada hasta tu decisión.
