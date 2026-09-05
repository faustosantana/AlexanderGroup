"""Helpers puros del importador (sin ORM)."""

from __future__ import annotations

from pathlib import Path


def commercial_partner_vals(
    name: str,
    vat_digits: str,
    country_id: int,
    *,
    batch: str | None = None,
    doc_type_id: int | None = None,
    field_names: set[str] | None = None,
) -> dict:
    """Vals mínimos de un contacto comercial dominicano con RNC.

    justech_do_has_rnc() exige is_company + país DO + VAT con formato 9–11 dígitos.
    No inventa correo, teléfono ni dirección.
    """
    fields = field_names or set()
    vals = {
        "name": name,
        "vat": vat_digits,
        "is_company": True,
        "company_type": "company",
        "customer_rank": 1,
        "company_id": False,
        "country_id": country_id,
    }
    if len(vat_digits) == 9 and "justech_do_partner_id_type" in fields:
        vals["justech_do_partner_id_type"] = "1"
    if "justech_do_fiscal_config_state" in fields:
        vals["justech_do_fiscal_config_state"] = "confirmed_history"
    if batch and "justech_do_fiscal_config_source" in fields:
        vals["justech_do_fiscal_config_source"] = batch
    if doc_type_id and "justech_do_default_document_type_id" in fields:
        vals["justech_do_default_document_type_id"] = doc_type_id
    if "l10n_do_dgii_tax_payer_type" in fields:
        vals["l10n_do_dgii_tax_payer_type"] = "taxpayer"
    return vals


def commercial_partner_fix_vals(
    existing: dict, field_names: set[str] | None = None
) -> dict:
    """Completa is_company / país / tipo RNC en un partner ya existente."""
    fields = field_names or set(existing)
    vals: dict = {}
    if not existing.get("is_company"):
        vals["is_company"] = True
        if "company_type" in fields or True:
            vals["company_type"] = "company"
    if existing.get("justech_do_fiscal_config_state") in (
        False,
        None,
        "pending_new",
        "needs_review",
    ):
        if (
            "justech_do_fiscal_config_state" in fields
            or "justech_do_fiscal_config_state" in existing
        ):
            vals["justech_do_fiscal_config_state"] = "confirmed_history"
    if (
        existing.get("justech_do_default_document_type_id") in (False, None, 0)
        and existing.get("_doc_type_id")
        and "justech_do_default_document_type_id" in fields
    ):
        vals["justech_do_default_document_type_id"] = existing["_doc_type_id"]
    if (
        len(str(existing.get("vat_digits") or "")) == 9
        and existing.get("justech_do_partner_id_type") not in ("1",)
        and "justech_do_partner_id_type" in fields
    ):
        vals["justech_do_partner_id_type"] = "1"
    return vals


def resolve_pdf_path(
    pdf_dir: str | Path,
    company_code: str,
    ncf: str,
    source_file: str | None = None,
    source_page: int | None = None,
) -> Path | None:
    """Localiza el PDF individual. Nunca abre un directorio como archivo."""
    root = Path(pdf_dir)
    if not root.is_dir():
        return None
    named = root / f"{company_code}_{ncf}.pdf"
    if _is_pdf_file(named):
        return named
    if source_file:
        candidate = root / source_file
        if _is_pdf_file(candidate):
            return candidate
        stem = Path(source_file).stem
        page = int(source_page or 1)
        for c in sorted(root.glob(f"{stem}*_page_{page:02d}.pdf")):
            if _is_pdf_file(c):
                return c
    for c in sorted(root.glob(f"*{ncf}*.pdf")):
        if _is_pdf_file(c):
            return c
    return None


def _is_pdf_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


CLEARING_CODE_CANDIDATES = ("11030205",)
CLEARING_NAME_MARKERS = (
    "other accounts receivable",
    "otras cuentas por cobrar",
    "cuentas por cobrar diversas",
    "cuenta transitoria",
    "cuentas transitorias",
    "migracion",
    "migración",
    "apertura",
)
CLEARING_NAME_FORBIDDEN = (
    "outstanding",
    "banreservas",
    "bank",
    "banco",
    "caja",
    "cash",
    "liquidity",
)


def is_opening_clearing_account(code: str | None, name: str | None) -> bool:
    """True si la cuenta del plan sirve para pagos históricos sin evidencia bancaria."""
    code_n = (code or "").strip()
    name_n = (name or "").strip().lower()
    if any(bad in name_n for bad in CLEARING_NAME_FORBIDDEN):
        return False
    if code_n in CLEARING_CODE_CANDIDATES:
        return True
    return any(marker in name_n for marker in CLEARING_NAME_MARKERS)
