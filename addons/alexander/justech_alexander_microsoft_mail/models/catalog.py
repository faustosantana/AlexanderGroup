"""Mapeo de correo Doralex: un dominio y un mailbox por empresa.

Se identifica la empresa por código corto / nombre, nunca por ID numérico.
"""

MAIL_PROFILES = (
    {
        "match": "DORALEX",
        "code": "DOR",
        "domain": "inversionesdoralex.com",
        "mailbox": "administracion@inversionesdoralex.com",
    },
    {
        "match": "PIÑARIA",
        "code": "PIN",
        "domain": "pinariagroup.com",
        "mailbox": "administracion@pinariagroup.com",
    },
    {
        "match": "DOMINION",
        "code": "DOM",
        "domain": "dominion-business.com",
        "mailbox": "administracion@dominion-business.com",
    },
    {
        "match": "MAYUMA",
        "code": "MAY",
        "domain": "elmayuma.com",
        "mailbox": "administracion@elmayuma.com",
    },
    {
        "match": "REMPART",
        "code": "REM",
        "domain": "rempartgroup.com",
        "mailbox": "administracion@rempartgroup.com",
    },
    {
        "match": "BLUE ELITE",
        "code": "BLU",
        "domain": "blueelite.net",
        "mailbox": "administracion@blueelite.net",
    },
)

ROLES = (
    "admin",
    "sales",
    "purchase",
    "invoice",
    "accounting",
    "info",
)

ROLE_LOCAL = {
    "admin": "administracion",
    "sales": "ventas",
    "purchase": "compras",
    "invoice": "facturacion",
    "accounting": "contabilidad",
    "info": "info",
}

ROLE_LABEL = {
    "admin": "Administración",
    "sales": "Ventas",
    "purchase": "Compras",
    "invoice": "Facturación",
    "accounting": "Contabilidad",
    "info": "Contacto",
}

MODEL_ROLE = {
    "sale.order": "sales",
    "sale.order.template": "sales",
    "crm.lead": "sales",
    "crm.phonecall": "sales",
    "purchase.order": "purchase",
    "purchase.requisition": "purchase",
    "account.payment": "accounting",
    "account.bank.statement": "accounting",
    "account.full.reconcile": "accounting",
}


def profile_for_code(code):
    code = (code or "").strip().upper()
    for profile in MAIL_PROFILES:
        if profile["code"] == code:
            return profile
    return None


def profile_for_company_name(name):
    hay = (name or "").upper()
    for profile in MAIL_PROFILES:
        if profile["match"] in hay:
            return profile
    return None


def all_domains():
    return tuple(profile["domain"] for profile in MAIL_PROFILES)


def address_for(profile, role):
    local = ROLE_LOCAL[role]
    return "%s@%s" % (local, profile["domain"])


def role_for_model(model, move_type=None):
    if model == "account.move":
        if move_type in ("out_invoice", "out_refund", "out_receipt"):
            return "invoice"
        if move_type in ("in_invoice", "in_refund", "in_receipt"):
            return "purchase"
        return "accounting"
    return MODEL_ROLE.get(model or "", "admin")


def domain_of(email):
    if not email or "@" not in email:
        return ""
    return email.rsplit("@", 1)[-1].strip().lower().strip(">")


def belongs_to_domain(email, domain):
    return domain_of(email) == (domain or "").lower()
