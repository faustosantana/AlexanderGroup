"""Detecta addons Enterprise 19 desde clon, archive oficial o .deb extraído."""

from __future__ import annotations

from pathlib import Path

# Ubuntu/Debian official installer (odoo.com → Odoo 19 → Ubuntu • Debian → Enterprise).
# Community nightlies look like odoo_19.0.YYYYMMDD_all.deb (no +e) and are rejected.


def manifest_version(module_dir: Path) -> str:
    text = (module_dir / "__manifest__.py").read_text(
        encoding="utf-8", errors="replace"
    )
    for line in text.splitlines():
        if "version" in line and "19." in line:
            return line.strip()
    return ""


def is_official_enterprise_package_name(name: str) -> bool:
    """True only for official Odoo 19 Enterprise artifacts (not Community nightly)."""
    n = Path(name).name.lower()
    if n.endswith(".deb"):
        if "19.0+" in n and "e" in n:
            return True
        if "19.0e" in n:
            return True
        if "enterprise" in n and "19" in n:
            return True
        return False
    if n.endswith((".zip", ".tar.gz", ".tgz", ".tar")):
        return any(m in n for m in ("+e", "enterprise", "19.0e"))
    return False


def find_official_enterprise_deb(archive_dir: Path) -> Path:
    if not archive_dir.is_dir():
        raise FileNotFoundError(f"No existe el directorio de archive: {archive_dir}")
    debs = sorted(
        p
        for p in archive_dir.iterdir()
        if p.is_file() and is_official_enterprise_package_name(p.name)
    )
    if not debs:
        raise FileNotFoundError(
            "No hay .deb Enterprise 19 oficial en el archive "
            "(se espera odoo_19.0+e.*_all.deb)."
        )
    return debs[-1]


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
