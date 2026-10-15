"""NCF expiration shown on Dominican invoices. Independent of quote validity."""

_ECF_SKIP_TAILS = ("32", "34")


def dx_ecf_skips_ncf_validity(is_ecf, doc_prefix="", ncf=""):
    if not is_ecf:
        return False
    ncf_key = "".join((doc_prefix or ncf or "").split()).upper().replace("-", "")
    if len(ncf_key) >= 3 and ncf_key[0] in ("E", "B"):
        return ncf_key[1:3] in _ECF_SKIP_TAILS
    return False


def dx_ncf_validity_label(is_ecf=False):
    return "Vencimiento e-NCF" if is_ecf else "Válida hasta"


def dx_pick_ncf_validity_date(*candidates):
    for value in candidates:
        if value:
            return value
    return False


def dx_ncf_prefix_and_seq(ncf=""):
    ncf_key = "".join((ncf or "").split()).upper().replace("-", "")
    if len(ncf_key) < 4 or not ncf_key[:3].isalnum():
        return "", False
    prefix = ncf_key[:3]
    digits = ncf_key[3:]
    if not digits.isdigit():
        return prefix, False
    return prefix, int(digits)
