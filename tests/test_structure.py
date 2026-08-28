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


def test_no_own_modules_in_shared() -> None:
    """addons/shared permanece vacío; los overlays viven en addons/alexander."""
    own = list((REPO_ROOT / "addons" / "shared").rglob("__manifest__.py"))
    assert not own, (
        "No deben existir módulos Odoo en addons/shared: "
        f"{[str(m.relative_to(REPO_ROOT)) for m in own]}"
    )


def test_alexander_modules_use_required_prefix() -> None:
    own = list((REPO_ROOT / "addons" / "alexander").rglob("__manifest__.py"))
    assert own, "Se esperan módulos justech_alexander_* en addons/alexander"
    for manifest in own:
        assert manifest.parent.name.startswith("justech_alexander_"), manifest
