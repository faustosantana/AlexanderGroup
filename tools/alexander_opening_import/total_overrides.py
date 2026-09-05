"""Overrides de total confirmados. No se inventan: solo lo autorizado."""

from __future__ import annotations

# 2026-09-05: el usuario confirmó que en B1500000150
# 249,792.00 es el subtotal, 44,962.56 el ITBIS y 294,754.56 el total.
# Excel había cargado 249,754.56 como monto original (ni el subtotal exacto).
PDF_TOTAL_OVERRIDES = {
    ("INVERSIONES DORALEX,S.RL.", "B1500000150"): {
        "reason": "USER_CONFIRMED_PDF_TOTAL_2026-09-05",
        "excel_original": "249754.56",
        "pdf_subtotal": "249792.00",
        "pdf_itbis": "44962.56",
        "pdf_total": "294754.56",
    }
}
