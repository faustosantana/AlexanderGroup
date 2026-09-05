"""Overrides de total confirmados. No se inventan: solo lo autorizado."""

from __future__ import annotations

# 2026-09-05: el usuario confirmó que en B1500000150
# 249,792.00 es el subtotal, 44,962.56 el ITBIS y 294,754.56 el total.
# Excel había cargado 249,754.56 como monto original (ni el subtotal exacto).
PDF_TOTAL_OVERRIDES = {
    ("INVERSIONES DORALEX,S.RL.", "B1500000150"): {
        "reason": "PDF_SOURCE_DOCUMENT_OVERRIDES_EXCEL_TRANSCRIPTION_ERROR",
        "excel_original": "249754.56",
        "pdf_subtotal": "249792.00",
        "pdf_itbis": "44962.56",
        "pdf_total": "294754.56",
    },
    ("REMPART GROUP S.R.L.", "B1500000110"): {
        "reason": "PDF_SOURCE_DOCUMENT_OVERRIDES_EXCEL_TRANSCRIPTION_ERROR",
        "excel_original": "267250.53",
        "pdf_total": "267250.52",
    },
}
