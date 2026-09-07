from __future__ import annotations

import re
import unicodedata

ADMIN_EXACT = {
    "subtotal",
    "sub total",
    "total",
    "total general",
    "importe general",
    "itbis",
    "itbis 18",
    "itbis 18%",
    "descuento",
    "forma de pago",
    "condiciones de pago",
    "tiempo de entrega",
    "validez de oferta",
    "rnc",
    "telefono",
    "teléfono",
    "correo",
    "cliente",
    "solicitado por",
    "fecha",
    "cotizacion",
    "cotización",
    "factura",
    "lote",
    "notas",
    "observaciones",
    "firma",
    "sello",
    "ncf",
    "orden",
    "no. orden",
    "pagina",
    "página",
}

ADMIN_PREFIX = (
    "subtotal",
    "total general",
    "importe",
    "forma de pago",
    "condicion",
    "validez",
    "tiempo de entrega",
    "observacion",
    "nota:",
    "firmado",
    "sello",
    "rnc:",
    "telefono:",
    "correo:",
    "cliente:",
    "solicitado",
)

STOP = {
    "de",
    "del",
    "la",
    "el",
    "los",
    "las",
    "y",
    "en",
    "con",
    "para",
    "por",
    "un",
    "una",
    "und",
    "ud",
    "unidad",
    "unidades",
}


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


def collapse(text: str) -> str:
    text = fold(text)
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"[|_•·]+", " ", text)
    text = re.sub(r"[^\w./\"%x×-]+", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_admin_text(text: str) -> bool:
    n = collapse(text)
    if not n:
        return True
    if n in ADMIN_EXACT:
        return True
    if any(n.startswith(p) for p in ADMIN_PREFIX):
        return True
    if n in {"cod", "item", "descripcion", "cantidad", "precio", "valor"}:
        return True
    return False


def title_es(text: str) -> str:
    raw = re.sub(r"\s+", " ", (text or "").strip())
    if not raw:
        return ""
    if len(raw) > 90:
        raw = raw[:90].rsplit(" ", 1)[0]
    parts = []
    for word in raw.split(" "):
        if re.fullmatch(r"[A-Z0-9./\"%-]{2,}", word) and any(
            ch.isdigit() for ch in word
        ):
            parts.append(word)
        elif word.isupper() and len(word) <= 6:
            parts.append(word)
        else:
            parts.append(word[:1].upper() + word[1:].lower() if word else word)
    return " ".join(parts)
