#!/usr/bin/env python3
"""Validador de módulos Odoo — Alexander Group.

Preparado para revisar módulos Odoo (Fase 5 en adelante). Hoy funciona aunque
todavía NO existan módulos: en ese caso termina correctamente (código 0).

Cuando existan módulos (directorios con `__manifest__.py` bajo `addons/`), valida
—de forma preliminar y ampliable— aspectos como:

    - Nombre técnico y prefijo (`justech_` / `justech_alexander_`).
    - Presencia y contenido básico del manifest.
    - Versión (formato Odoo `19.0.x.y.z`).
    - Licencia declarada.
    - Dependencias declaradas.
    - Presencia de archivos XML / CSV / seguridad / tests.
    - Referencias prohibidas (otros clientes) y URLs/credenciales hardcodeadas.
    - IDs de compañías fijos.

Códigos de salida:
    0  -> sin errores (incluye el caso "no hay módulos")
    1  -> se detectaron errores
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ADDONS_ROOT = REPO_ROOT / "addons"
ADDONS_AREAS = ["shared", "alexander", "third_party"]

VERSION_RE = re.compile(r"^19\.0\.\d+\.\d+\.\d+$")
URL_RE = re.compile(r"https?://[^\s'\"]+")
COMPANY_ID_RE = re.compile(r"(?i)\bcompany_id\b\s*[:=]\s*\d+")
SECRET_RE = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key)\b\s*[:=]\s*['\"][^'\"]+['\"]"
)

# Referencias prohibidas a otros clientes/entornos (ampliar según necesidad).
FORBIDDEN_REFERENCES = [
    "justgroup",
]

# Dominios/URLs permitidas dentro de manifests o código (documentación oficial).
ALLOWED_URL_HINTS = (
    "odoo.com",
    "example.com",
    "localhost",
    "doralexgroup.cloud",
    "microsoft.com",
    "microsoftonline.com",
    "office365.com",
)


class ModuleReport:
    def __init__(self, path: Path):
        self.path = path
        self.name = path.name
        self.errors: list[str] = []
        self.warnings: list[str] = []


def find_modules() -> list[Path]:
    modules: list[Path] = []
    if not ADDONS_ROOT.exists():
        return modules
    for area in ADDONS_AREAS:
        area_path = ADDONS_ROOT / area
        if not area_path.exists():
            continue
        for child in sorted(area_path.iterdir()):
            if child.is_dir() and (child / "__manifest__.py").exists():
                modules.append(child)
    return modules


def _area_of(module: Path) -> str:
    return module.parent.name


def _read_manifest(module: Path) -> dict | None:
    manifest_file = module / "__manifest__.py"
    try:
        return ast.literal_eval(manifest_file.read_text(encoding="utf-8"))
    except (SyntaxError, ValueError, OSError):
        return None


def validate_module(module: Path) -> ModuleReport:
    report = ModuleReport(module)
    area = _area_of(module)

    # Prefijo del nombre técnico (los de terceros están exentos).
    if area != "third_party" and not report.name.startswith("justech_"):
        report.errors.append(f"Nombre técnico sin prefijo 'justech_': {report.name}")
    if area == "alexander" and not report.name.startswith("justech_alexander_"):
        report.warnings.append(
            "Se recomienda el prefijo 'justech_alexander_' en addons/alexander"
        )

    manifest = _read_manifest(module)
    if manifest is None:
        report.errors.append("__manifest__.py ausente o no evaluable")
    else:
        version = str(manifest.get("version", ""))
        if not VERSION_RE.match(version):
            report.errors.append(
                f"Versión inválida '{version}' (esperado '19.0.x.y.z')"
            )
        if not manifest.get("license"):
            report.errors.append("Falta 'license' en el manifest")
        if "depends" not in manifest:
            report.warnings.append("El manifest no declara 'depends'")

    # Presencia de archivos habituales (solo advertencias).
    if not any(module.rglob("*.xml")):
        report.warnings.append("No contiene archivos XML")
    security_dir = module / "security"
    if not security_dir.exists():
        report.warnings.append("No contiene carpeta 'security/'")
    if not any(module.rglob("test_*.py")) and not (module / "tests").exists():
        report.warnings.append("No contiene pruebas")

    _scan_module_content(module, report)
    return report


def _scan_module_content(module: Path, report: ModuleReport) -> None:
    for path in module.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".py", ".xml", ".csv", ".yml", ".yaml", ".cfg"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        lower = text.lower()

        for ref in FORBIDDEN_REFERENCES:
            if ref in lower:
                report.errors.append(f"Referencia prohibida '{ref}' en {path.name}")

        if SECRET_RE.search(text):
            report.errors.append(f"Posible credencial hardcodeada en {path.name}")

        if COMPANY_ID_RE.search(text):
            report.warnings.append(f"company_id con ID fijo en {path.name}")

        for url in URL_RE.findall(text):
            if not any(hint in url for hint in ALLOWED_URL_HINTS):
                report.warnings.append(f"URL hardcodeada '{url}' en {path.name}")


def main() -> int:
    print("== Validación de módulos (Alexander Group) ==")
    modules = find_modules()

    if not modules:
        print("No hay módulos Odoo para validar todavía (Fase 0). Resultado: OK.")
        return 0

    total_errors = 0
    for module in modules:
        report = validate_module(module)
        total_errors += len(report.errors)
        status = "OK" if not report.errors else "FALLA"
        print(f"\n[{status}] {report.path.relative_to(REPO_ROOT)}")
        for err in report.errors:
            print(f"    ERROR: {err}")
        for warn in report.warnings:
            print(f"    aviso: {warn}")

    print(f"\nMódulos analizados: {len(modules)} | Errores: {total_errors}")
    if total_errors:
        print("Resultado: FALLA.")
        return 1
    print("Resultado: OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
