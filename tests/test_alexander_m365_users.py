"""Documentación y catálogo de usuarios M365/Odoo, sin secretos."""

from pathlib import Path

from tools.alexander_m365_users.catalog import (
    ALEXANDER_ADMIN_GROUPS,
    FORBIDDEN_SALES_ONLY_GROUPS,
    INVOICING_EXTRA_GROUPS,
    KIOSK_PART_NUMBERS,
    M365_DOMAIN,
    OPERATIONAL_COMPANY_IDS,
    PEOPLE,
    SALES_PURCHASE_GROUPS,
)

ROOT = Path("docs/users")
REQUIRED = {
    "00_scorecard.txt",
    "01_microsoft365.md",
    "02_odoo.md",
    "03_matrix.md",
    "04_rollback.md",
    "05_delivery_readiness.md",
}


def test_six_people_and_fixed_upns():
    assert len(PEOPLE) == 6
    assert M365_DOMAIN == "inversionesdoralex.com"
    upns = [p["upn"] for p in PEOPLE]
    assert upns == [
        "luis.aquino@inversionesdoralex.com",
        "janny.montero@inversionesdoralex.com",
        "elianny.sanchez@inversionesdoralex.com",
        "leopordo.jimenez@inversionesdoralex.com",
        "alexander.pina@inversionesdoralex.com",
        "geilin.rosario@inversionesdoralex.com",
    ]
    assert all(u.endswith("@" + M365_DOMAIN) for u in upns)
    assert {p["key"] for p in PEOPLE if p["invoicing"]} == {"alexander", "geilin"}
    assert next(p for p in PEOPLE if p["key"] == "alexander")["odoo_admin"] is True
    handoff = Path("tools/alexander_m365_users/generate_handoff_pack.py").read_text(
        encoding="utf-8"
    )
    assert '"odoo_pw_mode": "keep"' not in handoff


def test_kiosk_part_number_is_real_not_invented_id():
    assert KIOSK_PART_NUMBERS == ("EXCHANGEDESKLESS",)
    assert OPERATIONAL_COMPANY_IDS == (8, 9, 10, 11, 12, 13)


def test_least_privilege_groups():
    assert "account.group_account_invoice" not in SALES_PURCHASE_GROUPS
    assert "base.group_system" not in SALES_PURCHASE_GROUPS
    assert "account.group_account_invoice" in INVOICING_EXTRA_GROUPS
    assert "account.group_account_manager" not in INVOICING_EXTRA_GROUPS
    assert "base.group_system" in ALEXANDER_ADMIN_GROUPS
    assert "justech_approval_flow.group_self_approve" in FORBIDDEN_SALES_ONLY_GROUPS
    assert "justech_approval_flow.group_self_approve" not in ALEXANDER_ADMIN_GROUPS


def test_docs_exist_and_record_standard_trial_gate():
    names = {p.name for p in ROOT.iterdir() if p.is_file()}
    assert REQUIRED <= names
    score = (ROOT / "00_scorecard.txt").read_text(encoding="utf-8")
    assert "DOMAIN_VERIFIED = YES" in score
    assert "M365_USERS_CREATED = 6" in score
    assert "ODOO_DUPLICATES_CREATED = 0" in score
    assert "ALEXANDER_USER_ID = 5" in score
    assert "KIOSK_SKU = NOT_IN_TENANT" in score
    assert "STANDARD_SKU = O365_BUSINESS_PREMIUM" in score
    assert "MAILBOXES_READY = 6" in score
    assert "FINAL_USER_PROVISIONING_STATUS = SUCCESS_WITH_STANDARD_TRIAL" in score
    assert "DELIVERY_READY = YES" in score
    assert "FAUSTO_ACTIVE = YES" in score
    ready = (ROOT / "05_delivery_readiness.md").read_text(encoding="utf-8")
    assert "DELIVERY_READY = YES" in ready
    assert "fausto@justech.do" in ready
    audit = Path("tools/alexander_m365_users/delivery_readiness_audit.py").read_text(
        encoding="utf-8"
    )
    assert "ROLLBACK TO SAVEPOINT" in audit
    assert "env.cr.rollback()" in audit


def test_letter_is_justech_delivery_with_alexander_temp_password():
    text = Path("tools/alexander_m365_users/generate_client_letter.py").read_text(
        encoding="utf-8"
    )
    assert "JUSTECH" in text
    assert "Justech-text-logo.png" in text
    assert "DOR.png" not in text
    assert '"odoo_pw": ODOO_PW' in text
    assert "La contraseña de Odoo que usted ya usa" not in text


def test_docs_and_catalog_have_no_secrets():
    banned = (
        "BEGIN PRIVATE",
        "Doralex#M365",
        "Doralex#Odoo",
        "eyJ",
        "AKIA",
    )
    for path in [*ROOT.glob("*"), *Path("tools/alexander_m365_users").glob("*.py")]:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, path
