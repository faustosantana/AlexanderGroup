from __future__ import annotations

import hashlib
from pathlib import Path

from openpyxl import load_workbook

from .classify import document_type
from .textutil import collapse, is_admin_text  # collapse used by detect_currency

SOURCE_DIR = Path("/home/ubuntu/.cursor/projects/workspace/uploads")

HEADER_ALIASES = {
    "desc": (
        "descripcion",
        "descripción",
        "articulo",
        "artículo",
        "producto",
        "detalle",
        "concepto",
    ),
    "qty": ("cantidad", "cant", "cant.", "pieza/cant", "pieza/cant.", "qty", "cantid"),
    "uom": ("und", "und.", "ud", "unidad", "u.m", "um", "medida"),
    "price_excl": (
        "precio unit sin itbis",
        "precio unitario sin itbis",
        "p.u. sin itbis",
        "pu sin itbis",
    ),
    "price": (
        "precio unit",
        "precio unitario",
        "p.u.",
        "p.u",
        "pu",
        "precio",
        "precio u",
    ),
    "itbis": ("itbis", "itbis (18%)", "itbis 18%", "impuesto"),
    "subtotal": ("subtotal", "sub total", "valor", "importe"),
    "total": ("total", "total rd", "total general linea"),
    "code": ("cod", "cod.", "codigo", "código", "item", "ítem", "no"),
}


def detect_currency(preview: str) -> str:
    blob = collapse(preview)
    has_usd = any(x in blob for x in (" usd", "us$", "dolares", "dólares", "dollar"))
    has_dop = any(x in blob for x in (" dop", "rd$", "pesos"))
    if has_usd and not has_dop:
        return "USD"
    if has_usd and has_dop:
        return "MIXED"
    return "DOP"


def _looks_like_headerless_line(row: list) -> dict | None:
    """Fallback for sheets that start with item/code/desc/qty/uom/price without headers."""
    cells = [_as_text(c) for c in row]
    if len(cells) < 4:
        return None
    nonempty = [(i, c) for i, c in enumerate(cells) if c]
    if len(nonempty) < 3:
        return None
    texts = [(i, c) for i, c in nonempty if _to_float(c) is None and len(c) >= 4]
    nums = [(i, _to_float(c)) for i, c in nonempty if _to_float(c) is not None]
    if not texts or len(nums) < 2:
        return None
    desc_i, desc = max(texts, key=lambda x: len(x[1]))
    if is_admin_text(desc) or len(desc) < 4:
        return None
    after = [(i, v) for i, v in nums if i > desc_i]
    if len(after) < 2:
        return None
    qty = after[0][1]
    price = after[1][1]
    total = after[-1][1] if len(after) >= 3 else None
    uom = ""
    for i, c in nonempty:
        if desc_i < i < after[0][0] and _to_float(c) is None:
            uom = c
            break
    return {
        "desc_i": desc_i,
        "desc": desc,
        "qty": qty,
        "uom": uom,
        "raw_price": price,
        "total": total,
    }


def source_files(directory: Path = SOURCE_DIR) -> list[dict]:
    files = []
    for path in sorted(directory.glob("*.xlsx")):
        name = path.name.upper()
        if not any(k in name for k in ("COT", "FORMATO", "MARCELINO")):
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append(
            {
                "path": str(path),
                "name": path.name,
                "size": path.stat().st_size,
                "sha256": digest,
            }
        )
    seen = {}
    unique = []
    skipped = []
    for rec in files:
        if rec["sha256"] in seen:
            skipped.append({**rec, "duplicate_of": seen[rec["sha256"]]})
            continue
        seen[rec["sha256"]] = rec["name"]
        unique.append(rec)
    return unique, skipped


def _as_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_float(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("$", "").replace("RD", "").replace(",", "")
    text = text.replace(" ", "")
    if not text or text in {"-", "N/A"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _score_header(values: list[str]) -> tuple[int, dict]:
    mapped = {}
    score = 0
    for idx, raw in enumerate(values):
        key = collapse(raw).replace(".", "")
        for field, aliases in HEADER_ALIASES.items():
            if field in mapped:
                continue
            if key in {collapse(a).replace(".", "") for a in aliases} or any(
                collapse(a).replace(".", "") == key for a in aliases
            ):
                mapped[field] = idx
                score += 3 if field in {"desc", "price", "price_excl", "qty"} else 1
    return score, mapped


def detect_header(rows: list[list]) -> tuple[int | None, dict]:
    best = (0, None, {})
    for i, row in enumerate(rows[:45]):
        texts = [_as_text(c) for c in row]
        score, mapped = _score_header(texts)
        if "desc" in mapped and score > best[0]:
            best = (score, i, mapped)
    if best[0] >= 4 and "desc" in best[2]:
        return best[1], best[2]
    return None, {}


def extract_workbook(
    path: Path, display_name: str
) -> tuple[list[dict], list[dict], int]:
    wb = load_workbook(path, read_only=True, data_only=True)
    sheets = []
    candidates = []
    admin_ignored = 0
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = []
        for row in ws.iter_rows(values_only=True):
            rows.append(list(row))
        nonempty = sum(1 for r in rows if any(_as_text(c) for c in r))
        preview = " ".join(
            _as_text(c) for r in rows[:20] for c in r[:8] if _as_text(c)
        )[:400]
        dtype = document_type(sheet_name, preview) if nonempty else "EMPTY"
        header_idx, mapping = detect_header(rows) if nonempty else (None, {})
        has_lines = bool(mapping.get("desc") is not None and nonempty > 2)
        sheets.append(
            {
                "file": display_name,
                "sheet": sheet_name,
                "rows": nonempty,
                "columns": max((len(r) for r in rows), default=0),
                "document_type": dtype,
                "has_product_lines": has_lines,
                "header_row": header_idx,
                "status": "PROCESSED" if nonempty else "EMPTY",
            }
        )
        if not has_lines:
            fallback_hits = 0
            for ridx, row in enumerate(rows, start=1):
                parsed = _looks_like_headerless_line(row)
                if not parsed:
                    continue
                fallback_hits += 1
                candidates.append(
                    {
                        "source_file": display_name,
                        "source_sheet": sheet_name,
                        "source_row": ridx,
                        "document_type": dtype if dtype != "EMPTY" else "PRODUCT_LIST",
                        "raw_description": parsed["desc"],
                        "quantity": parsed["qty"],
                        "uom_raw": parsed["uom"],
                        "raw_unit_price": parsed["raw_price"],
                        "price_excl_hint": None,
                        "itbis": None,
                        "subtotal": None,
                        "total": parsed["total"],
                        "currency": detect_currency(preview),
                    }
                )
            if fallback_hits:
                sheets[-1]["has_product_lines"] = True
                sheets[-1]["status"] = "PROCESSED_HEADERLESS"
            continue
        desc_i = mapping["desc"]
        for ridx, row in enumerate(rows[header_idx + 1 :], start=header_idx + 2):
            desc = _as_text(row[desc_i] if desc_i < len(row) else "")
            if not desc:
                continue
            if is_admin_text(desc):
                admin_ignored += 1
                continue
            if len(desc) < 3:
                continue
            qty = (
                _to_float(row[mapping["qty"]])
                if "qty" in mapping and mapping["qty"] < len(row)
                else None
            )
            uom = (
                _as_text(row[mapping["uom"]])
                if "uom" in mapping and mapping["uom"] < len(row)
                else ""
            )
            raw_price = None
            price_excl = None
            if "price_excl" in mapping and mapping["price_excl"] < len(row):
                price_excl = _to_float(row[mapping["price_excl"]])
            if "price" in mapping and mapping["price"] < len(row):
                raw_price = _to_float(row[mapping["price"]])
            itbis = (
                _to_float(row[mapping["itbis"]])
                if "itbis" in mapping and mapping["itbis"] < len(row)
                else None
            )
            subtotal = (
                _to_float(row[mapping["subtotal"]])
                if "subtotal" in mapping and mapping["subtotal"] < len(row)
                else None
            )
            total = (
                _to_float(row[mapping["total"]])
                if "total" in mapping and mapping["total"] < len(row)
                else None
            )
            candidates.append(
                {
                    "source_file": display_name,
                    "source_sheet": sheet_name,
                    "source_row": ridx,
                    "document_type": dtype,
                    "raw_description": desc,
                    "quantity": qty,
                    "uom_raw": uom,
                    "raw_unit_price": raw_price,
                    "price_excl_hint": price_excl,
                    "itbis": itbis,
                    "subtotal": subtotal,
                    "total": total,
                    "currency": detect_currency(preview),
                }
            )
    wb.close()
    return sheets, candidates, admin_ignored


def extract_all(directory: Path = SOURCE_DIR) -> tuple[list[dict], list[dict], dict]:
    unique, skipped = source_files(directory)
    all_sheets: list[dict] = []
    all_cands: list[dict] = []
    admin_ignored = 0
    raw_scanned = 0
    for rec in unique:
        sheets, cands, ignored = extract_workbook(Path(rec["path"]), rec["name"])
        all_sheets.extend(sheets)
        all_cands.extend(cands)
        admin_ignored += ignored
        raw_scanned += sum(s["rows"] for s in sheets)
    stats = {
        "files_received": len(unique) + len(skipped),
        "unique_files": len(unique),
        "duplicate_files": len(skipped),
        "skipped_files": [s["name"] for s in skipped],
        "unique_file_names": [u["name"] for u in unique],
        "raw_rows_scanned": raw_scanned,
        "raw_product_candidates": len(all_cands),
        "administrative_rows_ignored": admin_ignored,
        "service_rows": 0,  # filled after enrich
    }
    return all_sheets, all_cands, stats
