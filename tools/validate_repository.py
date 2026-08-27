#!/usr/bin/env python3
"""Validador de seguridad y estructura del repositorio — Alexander Group.

Verifica que el repositorio no contenga artefactos sensibles y que exista la
estructura mínima requerida. Solo usa la biblioteca estándar. NO borra archivos:
únicamente reporta hallazgos.

Códigos de salida:
    0  -> sin hallazgos (repositorio válido)
    1  -> se detectaron riesgos o falta estructura mínima
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Directorios que nunca se inspeccionan.
SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
}

# Extensiones prohibidas (artefactos que nunca deben estar en Git).
FORBIDDEN_EXTENSIONS = {
    ".sql",
    ".dump",
    ".backup",
    ".pem",
    ".key",
    ".crt",
    ".pfx",
    ".p12",
}

# Tamaño máximo razonable por archivo (5 MB).
MAX_FILE_BYTES = 5 * 1024 * 1024

# Estructura mínima requerida (relativa a la raíz del repositorio).
REQUIRED_PATHS = [
    "addons/shared",
    "addons/alexander",
    "addons/third_party",
    "config",
    "deployment",
    "docs",
    "migrations",
    "tests",
    "tools",
    "README.md",
    ".gitignore",
    "SECURITY.md",
    "CONTRIBUTING.md",
]

# Detección de secretos evidentes: clave = valor literal real.
# - El prefijo/sufijo opcional de caracteres de palabra permite detectar claves
#   como `db_password`, `ODOO_ADMIN_PASSWD` o `smtp_token`.
# - `[:=](?!=)` evita coincidir con separadores decorativos como `==` o `===`.
SECRET_KEY_RE = re.compile(
    r"(?i)(?:^|[^A-Za-z0-9_])[A-Za-z0-9_]*"
    r"(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|"
    r"private[_-]?key)[A-Za-z0-9_]*\s*[:=](?!=)\s*(?P<val>\S.*)$"
)

# Interpolación de variables/entorno: NO es un secreto literal (es la forma
# correcta de manejar credenciales), por lo que se ignora en el escaneo.
SHELL_INTERPOLATION_RE = re.compile(r"\$\{|\$\(")

# Valores que NO se consideran secretos reales (placeholders / vacíos).
PLACEHOLDER_RE = re.compile(
    r"(?i)^(|changeme.*|change_me.*|<.*>|\$\{.*\}|xxx+|\*+|none|null|"
    r"your[_-].*|example.*|placeholder.*|tu[_-].*|pendiente.*)$"
)

# Bloque PEM de clave privada embebida en cualquier archivo de texto.
PRIVATE_KEY_BLOCK_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")

# No se escanea el contenido de estos archivos/directorios para secretos:
# - *.example (plantillas por diseño)
# - tools/ (este validador contiene las propias expresiones de detección)
CONTENT_SCAN_SKIP_DIRS = {"tools"}


def iter_files(root: Path):
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            yield path


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def is_env_real(path: Path) -> bool:
    """True si es un .env real (no .env.example)."""
    name = path.name
    if name == ".env":
        return True
    if name.startswith(".env.") and not name.endswith(".example"):
        return True
    return False


def check_structure(findings: list[str]) -> None:
    for rel_path in REQUIRED_PATHS:
        if not (REPO_ROOT / rel_path).exists():
            findings.append(f"[ESTRUCTURA] Falta la ruta requerida: {rel_path}")


def check_files(findings: list[str]) -> None:
    for path in iter_files(REPO_ROOT):
        parts = path.relative_to(REPO_ROOT).parts

        # Carpeta filestore en cualquier nivel.
        if "filestore" in parts:
            findings.append(f"[FILESTORE] Carpeta filestore no permitida: {rel(path)}")

        # .env real.
        if is_env_real(path):
            findings.append(f"[SECRETO] Archivo .env real no permitido: {rel(path)}")

        # Extensión prohibida.
        if path.suffix.lower() in FORBIDDEN_EXTENSIONS:
            findings.append(
                f"[ARTEFACTO] Extensión prohibida '{path.suffix}': {rel(path)}"
            )

        # Tamaño máximo.
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        if size > MAX_FILE_BYTES:
            findings.append(
                f"[TAMAÑO] Archivo mayor a {MAX_FILE_BYTES} bytes "
                f"({size} bytes): {rel(path)}"
            )

        _scan_content(path, parts, findings)


def _scan_content(path: Path, parts: tuple[str, ...], findings: list[str]) -> None:
    # No escanear plantillas ni el propio validador.
    if path.name.endswith(".example"):
        return
    if parts and parts[0] in CONTENT_SCAN_SKIP_DIRS:
        return
    if path.suffix.lower() in FORBIDDEN_EXTENSIONS:
        return

    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return  # binario o ilegible: se ignora para el escaneo de texto.

    # Código de terceros vendorizado (importado de Justgroup): se revisa aparte y
    # contiene definiciones de campos `token/password`, generadores `secrets.*` y
    # lecturas de `os.environ`/`context.get` que NO son secretos literales. Se
    # omite la heurística de palabra-clave, pero SÍ se detecta material de clave
    # privada embebido (bloques PEM), que nunca es aceptable.
    is_vendored = len(parts) >= 2 and parts[0] == "addons" and parts[1] == "third_party"

    for lineno, line in enumerate(text.splitlines(), start=1):
        if PRIVATE_KEY_BLOCK_RE.search(line):
            findings.append(
                f"[CLAVE] Bloque de clave privada embebido: {rel(path)}:{lineno}"
            )

        if is_vendored:
            continue

        # Las referencias a variables/entorno (${VAR}, $(...)) no son secretos.
        if SHELL_INTERPOLATION_RE.search(line):
            continue

        match = SECRET_KEY_RE.search(line)
        if match:
            raw = match.group("val").strip()
            tokens = raw.split()
            value = tokens[0].strip("'\"").strip() if tokens else ""
            if value and not PLACEHOLDER_RE.match(value):
                findings.append(
                    f"[SECRETO] Posible credencial/token con valor real: "
                    f"{rel(path)}:{lineno}"
                )


def main() -> int:
    findings: list[str] = []
    check_structure(findings)
    check_files(findings)

    print("== Validación de repositorio (Alexander Group) ==")
    print(f"Raíz: {REPO_ROOT}")
    if findings:
        print(f"\nHALLAZGOS ({len(findings)}):")
        for item in findings:
            print(f"  - {item}")
        print("\nResultado: FALLA. Corrige los hallazgos antes de continuar.")
        return 1

    print("\nResultado: OK. No se detectaron riesgos y la estructura mínima existe.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
