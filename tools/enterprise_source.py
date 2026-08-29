"""Detecta el árbol de addons Enterprise 19 a partir de un clon o un archive oficial."""

from __future__ import annotations

from pathlib import Path

REQUIRED_SIBLINGS = ("web_enterprise",)


def manifest_version(module_dir: Path) -> str:
    text = (module_dir / "__manifest__.py").read_text(
        encoding="utf-8", errors="replace"
    )
    for line in text.splitlines():
        if "version" in line and "19." in line:
            return line.strip()
    return ""


def find_enterprise_addons_root(extract_dir: Path) -> Path:
    """Devuelve el directorio que contiene web_enterprise/ como módulo."""
    candidates: list[Path] = []
    for manifest in extract_dir.rglob("web_enterprise/__manifest__.py"):
        parent = manifest.parent.parent
        if (parent / "web_enterprise" / "__manifest__.py").is_file():
            candidates.append(parent)
    if not candidates:
        raise FileNotFoundError("No se encontró web_enterprise en el archive/clon.")
    candidates.sort(
        key=lambda p: (0 if (p / "account_accountant").is_dir() else 1, len(p.parts))
    )
    root = candidates[0]
    if not manifest_version(root / "web_enterprise"):
        raise ValueError("web_enterprise no declara versión 19.x")
    return root
