"""Parte PDFs multifatura en páginas individuales sin alterar el original."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pypdf import PdfReader, PdfWriter


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def split_source_pdfs(sources: list[Path], dest_dir: Path) -> list[dict]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    inventory = []
    for src in sources:
        reader = PdfReader(str(src))
        pages = len(reader.pages)
        rec = {
            "SOURCE_FILE": src.name,
            "path": str(src),
            "sha256": sha256(src),
            "pages": pages,
            "split": [],
        }
        for i, page in enumerate(reader.pages, start=1):
            writer = PdfWriter()
            writer.add_page(page)
            out = dest_dir / f"{src.stem}_page_{i:02d}.pdf"
            with out.open("wb") as fh:
                writer.write(fh)
            rec["split"].append(
                {
                    "page": i,
                    "path": str(out),
                    "sha256": sha256(out),
                    "bytes": out.stat().st_size,
                }
            )
        inventory.append(rec)
    (dest_dir / "split_inventory.json").write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return inventory


def rename_individual(
    src_page: Path, dest_dir: Path, company_code: str, ncf: str
) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{company_code}_{ncf}.pdf"
    dest.write_bytes(src_page.read_bytes())
    return dest
