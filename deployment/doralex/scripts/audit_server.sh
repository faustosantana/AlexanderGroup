#!/usr/bin/env bash
# Doralex — AUDITORIA DE SERVIDOR (SOLO LECTURA).
# ==============================================================================
# NO instala ni modifica NADA. Solo inspecciona y produce un informe en Markdown
# apto para pegar/actualizar docs/infrastructure/SERVER_AUDIT.md.
#
# Uso (en el servidor, tras autorizar SSH):
#   bash audit_server.sh > /opt/doralex/SERVER_AUDIT_$(date +%Y%m%d_%H%M%S).md
# ==============================================================================
set -uo pipefail

have() { command -v "$1" >/dev/null 2>&1; }
section() { printf '\n## %s\n\n' "$1"; }
# Comillas simples intencionales: el formato de printf es literal (no expande).
# shellcheck disable=SC2016
code() { printf '```\n%s\n```\n' "${1:-(sin datos)}"; }
run() { "$@" 2>/dev/null || echo "(no disponible)"; }

printf '# Doralex — Auditoría de servidor\n\n'
printf -- '- Fecha: %s\n' "$(date -u +'%Y-%m-%d %H:%M:%SZ')"
printf -- '- Ejecutado por: %s@%s\n' "$(id -un)" "$(hostname 2>/dev/null || echo '?')"
printf -- '- Modo: SOLO LECTURA (sin cambios)\n'

section "Hostname / OS"
code "$(run hostnamectl 2>/dev/null || { echo "hostname: $(hostname)"; run cat /etc/os-release; })"

section "Kernel / Arquitectura"
code "$(run uname -a)"

section "CPU"
code "$(run lscpu | sed -n '1,20p')"

section "Memoria (RAM)"
code "$(run free -h)"

section "Swap"
code "$(run swapon --show)"

section "Disco"
code "$(run df -hT)"

section "Mounts"
code "$(run findmnt -A 2>/dev/null || run mount)"

section "Red (interfaces / IP)"
code "$(run ip -brief address 2>/dev/null || run ifconfig -a)"

section "Puertos en escucha"
if have ss; then code "$(run ss -tulpn)"; else code "$(run netstat -tulpn)"; fi

section "Firewall"
{
  if have ufw; then echo "== ufw =="; run ufw status verbose; fi
  if have nft; then echo "== nftables =="; run nft list ruleset; fi
  if have iptables; then echo "== iptables =="; run iptables -S; fi
} > /tmp/_dx_fw 2>/dev/null
code "$(cat /tmp/_dx_fw 2>/dev/null)"; rm -f /tmp/_dx_fw

section "Servicios activos (systemd)"
code "$(run systemctl list-units --type=service --state=running --no-pager --no-legend | awk '{print $1}')"

section "Docker"
if have docker; then
  code "$(run docker --version; run docker compose version; echo '--- contenedores ---'; run docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'; echo '--- volúmenes ---'; run docker volume ls; echo '--- redes ---'; run docker network ls)"
else
  code "Docker NO instalado"
fi

section "PostgreSQL (host)"
if have psql || have pg_lsclusters; then
  code "$(run pg_lsclusters; run psql --version)"
else
  code "PostgreSQL de host NO detectado (puede ir en contenedor)"
fi

section "Reverse proxy (Nginx / Traefik)"
{
  if have nginx; then echo "== nginx =="; run nginx -v; fi
  if have traefik; then echo "== traefik =="; run traefik version; fi
  if ! have nginx && ! have traefik; then echo "Ninguno detectado en host"; fi
} > /tmp/_dx_rp 2>&1
code "$(cat /tmp/_dx_rp 2>/dev/null)"; rm -f /tmp/_dx_rp

section "Certificados (Let's Encrypt)"
code "$(run ls -1 /etc/letsencrypt/live 2>/dev/null || echo 'Sin /etc/letsencrypt/live')"

section "Usuarios (con shell de login)"
code "$(run getent passwd | awk -F: '$7 ~ /(bash|sh|zsh)$/ {print $1\" -> \"$7}')"

section "Timezone / Locale"
code "$(run timedatectl 2>/dev/null; echo '--- locale ---'; run locale)"

section "SSH (configuración efectiva, sin secretos)"
code "$(run sshd -T 2>/dev/null | grep -Ei 'permitrootlogin|passwordauthentication|pubkeyauthentication|port|x11forwarding' || run grep -Ei '^(PermitRootLogin|PasswordAuthentication|PubkeyAuthentication|Port)' /etc/ssh/sshd_config)"

section "Espacio disponible (resumen)"
code "$(run df -h --output=source,fstype,size,used,avail,pcent,target 2>/dev/null || run df -h)"

section "Snapshots / Provider (si aplica)"
code "$(run ls -1 /var/lib/snapshots 2>/dev/null; run cloud-init query -a 2>/dev/null | head -40; echo '(revisar panel del proveedor manualmente)')"

printf '\n---\n_Fin de la auditoría (solo lectura)._\n'
