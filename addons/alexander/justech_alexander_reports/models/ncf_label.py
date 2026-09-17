"""Dominican fiscal-number captions. Never a generic NCF on customer invoices."""

_DX_NCF_LABELS = {
    "fiscal": "Número de Comprobante Fiscal",
    "governmental": "Número de Comprobante Gubernamental",
    "special": "Número de Comprobante de Régimen Especial",
}


def _dx_norm_token(value):
    return "".join((value or "").split()).upper().replace("-", "")


def dx_ncf_kind(ncf="", ncf_type="", type_name=""):
    ncf_type_key = (ncf_type or "").strip().lower().replace("e-", "")
    if ncf_type_key in ("governmental", "15", "45"):
        return "governmental"
    if ncf_type_key in ("special", "14", "44"):
        return "special"
    name = (type_name or "").lower()
    if "gubernamental" in name:
        return "governmental"
    if "régimen especial" in name or "regimen especial" in name:
        return "special"
    prefix = _dx_norm_token(ncf)[:3]
    if prefix in ("B15", "E45"):
        return "governmental"
    if prefix in ("B14", "E44"):
        return "special"
    return "fiscal"


def dx_ncf_affected_label(kind="fiscal"):
    return "%s afectado" % dx_ncf_label(kind)


def dx_ncf_label(kind="fiscal", pending=False):
    label = _DX_NCF_LABELS.get(kind) or _DX_NCF_LABELS["fiscal"]
    if pending:
        return "Pendiente de %s" % label.lower()
    return label
