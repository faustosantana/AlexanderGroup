#!/usr/bin/env python3
"""Escáner de higiene de módulos Odoo — Doralex.

Analiza uno o varios directorios de módulos Odoo en busca de "hardcodes" que
impiden la reutilización multiempresa o que acoplan el código a Justech/Justgroup.
Pensado para revisar módulos custom ANTES de copiarlos a AlexanderGroup.

Detecta (heurística, revisar manualmente los hallazgos):
    - company_id asignado a un entero literal (compañía fija).
    - Referencias a dominios/entornos de Justech (justgroup.app, justech.do, etc.).
    - Correos hardcodeados (@justech.do u otros literales).
    - URLs http(s) hardcodeadas (salvo odoo.com / localhost).
    - Posibles RNC hardcodeados (secuencias de 9-11 dígitos cerca de rnc/vat).

Uso:
    python tools/scan_module_hygiene.py <dir> [<dir> ...]
    python tools/scan_module_hygiene.py deployment/doralex   # (por defecto: custom-addons si existe)

Códigos de salida:
    0  -> sin hallazgos (o sin módulos que analizar)
    1  -> se detectaron hardcodes a revisar
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCAN_EXT = {".py", ".xml", ".csv", ".yml", ".yaml", ".cfg"}

PATTERNS = [
    ("COMPANY_ID_FIJO", re.compile(r"(?i)\bcompany_id\b\s*[:=]\s*\d+")),
    (
        "JUSTECH_REF",
        re.compile(r"(?i)\b(justgroup\.app|justech\.do|justgroup|justech)\b"),
    ),
    (
        "EMAIL_HARDCODE",
        re.compile(r"(?i)[a-z0-9._%+-]+@(?!example\.com)[a-z0-9.-]+\.[a-z]{2,}"),
    ),
    (
        "URL_HARDCODE",
        re.compile(
            r"(?i)https?://(?!(?:www\.)?odoo\.com|localhost|127\.0\.0\.1)[^\s'\"<>]+"
        ),
    ),
    ("RNC_HARDCODE", re.compile(r"(?i)\b(rnc|vat)\b[^0-9]{0,12}\d{9,11}\b")),
]


def find_modules(root: Path) -> list[Path]:
    if (root / "__manifest__.py").exists():
        return [root]
    return sorted({m.parent for m in root.rglob("__manifest__.py")})


def scan_file(path: Path, findings: list[str]) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return
    for lineno, line in enumerate(text.splitlines(), start=1):
        for label, rx in PATTERNS:
            if rx.search(line):
                findings.append(f"[{label}] {path}:{lineno}: {line.strip()[:120]}")


def main(argv: list[str]) -> int:
    args = argv[1:]
    if not args:
        default = Path("deployment/doralex")
        args = [str(default)]
    roots = [Path(a) for a in args]

    modules: list[Path] = []
    for r in roots:
        if r.exists():
            modules.extend(find_modules(r))

    print("== Escáner de higiene de módulos (Doralex) ==")
    if not modules:
        print(
            "No se encontraron módulos Odoo (con __manifest__.py) en:",
            ", ".join(str(r) for r in roots),
        )
        print("Resultado: OK (nada que analizar).")
        return 0

    findings: list[str] = []
    for m in modules:
        for f in m.rglob("*"):
            if f.is_file() and f.suffix.lower() in SCAN_EXT:
                scan_file(f, findings)

    print(f"Módulos analizados: {len(modules)}")
    if findings:
        print(f"\nHALLAZGOS ({len(findings)}) — revisar y adaptar antes de reutilizar:")
        for item in findings:
            print(f"  - {item}")
        print(
            "\nResultado: HALLAZGOS. Adaptar (multiempresa/configurable) antes de copiar."
        )
        return 1

    print("Resultado: OK. Sin hardcodes evidentes.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
