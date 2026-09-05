#!/usr/bin/env python3
"""Crea <EMPRESA>_<NCF>.pdf por factura detectada, sin alterar originales."""

from __future__ import annotations

import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from tools.alexander_opening_import.b001_catalog import B001_INVOICES
from tools.alexander_opening_import.scan_catalog import SCAN_INVOICES
from tools.alexander_opening_import.split_pdfs import sha256

CODE = {
    "INVERSIONES DORALEX,S.RL.": "DORALEX",
    "INVERSIONES EL MAYUMA, S.R.L.": "MAYUMA",
    "REMPART GROUP S.R.L.": "REMPART",
}

# uploaded filename → catalog source_file
UPLOAD_MAP = {
    "DORALEX-CXC-FACT-B15.pdf": "DORALEX-CXC-FACT-B15_cc82.pdf",
    "DORALEX-CXC-FACT-B001.pdf": "DORALEX-CXC-FACT-B001_a53b.pdf",
    "MAYUMA-CXC-FACT-B15.pdf": "MAYUMA-CXC-FACT-B15_1e65.pdf",
    "REMPART-CXC-FACT-B15.pdf": "REMPART-CXC-FACT-B15_f167.pdf",
}


def extract_pages(src: Path, pages: list[int], dest: Path):
    reader = PdfReader(str(src))
    writer = PdfWriter()
    for p in pages:
        writer.add_page(reader.pages[p - 1])
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as fh:
        writer.write(fh)


def main():
    uploads = Path(
        sys.argv[1]
        if len(sys.argv) > 1
        else "/home/ubuntu/.cursor/projects/workspace/uploads"
    )
    dest = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/alexander_opening_pdfs")
    dest.mkdir(parents=True, exist_ok=True)
    # keep originals
    for src_name, uploaded in UPLOAD_MAP.items():
        src = uploads / uploaded
        if src.exists():
            copy = dest / src_name
            copy.write_bytes(src.read_bytes())
    invoices = list(SCAN_INVOICES) + list(B001_INVOICES)
    written = []
    for inv in invoices:
        pages = inv.get("source_pages") or [inv["source_page"]]
        src_logical = inv["source_file"]
        uploaded = uploads / UPLOAD_MAP[src_logical]
        code = CODE[inv["company"]]
        out = dest / f"{code}_{inv['ncf']}.pdf"
        extract_pages(uploaded, pages, out)
        written.append(
            {
                "file": out.name,
                "pages": pages,
                "sha256": sha256(out),
                "bytes": out.stat().st_size,
            }
        )
        print(out.name, pages, out.stat().st_size)
    print("NAMED_PDFS", len(written))


if __name__ == "__main__":
    main()
