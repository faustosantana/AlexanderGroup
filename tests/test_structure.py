"""Pruebas de estructura del repositorio — Alexander Group (Fase 0).

Verifican que exista la estructura mínima requerida. No dependen de Odoo ni se
conectan a servicios externos. Ejecutar con `pytest`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_DIRS = [
    "addons/shared",
    "addons/alexander",
    "addons/third_party",
    "config",
    "deployment",
    "docs",
    "migrations",
    "tests",
    "tools",
]

REQUIRED_FILES = [
    "README.md",
    ".gitignore",
    "SECURITY.md",
    "CONTRIBUTING.md",
]


@pytest.mark.parametrize("rel_dir", REQUIRED_DIRS)
def test_required_directory_exists(rel_dir: str) -> None:
    path = REPO_ROOT / rel_dir
    assert path.is_dir(), f"Falta el directorio requerido: {rel_dir}"


@pytest.mark.parametrize("rel_file", REQUIRED_FILES)
def test_required_file_exists(rel_file: str) -> None:
    path = REPO_ROOT / rel_file
    assert path.is_file(), f"Falta el archivo requerido: {rel_file}"


def test_addons_areas_have_readme() -> None:
    for area in ("shared", "alexander", "third_party"):
        readme = REPO_ROOT / "addons" / area / "README.md"
        assert readme.is_file(), f"Falta README en addons/{area}"


def test_no_functional_odoo_modules_yet() -> None:
    """En Fase 0 no debe existir ningún módulo Odoo funcional (sin __manifest__.py)."""
    manifests = list((REPO_ROOT / "addons").rglob("__manifest__.py"))
    assert not manifests, (
        "No deben existir módulos Odoo funcionales en Fase 0: "
        f"{[str(m.relative_to(REPO_ROOT)) for m in manifests]}"
    )
