"""Pruebas de mapeo Microsoft mail (sin secretos ni IDs de compañía)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MODULE = REPO / "addons" / "alexander" / "justech_alexander_microsoft_mail"


def _catalog():
    spec = importlib.util.spec_from_file_location(
        "dx_mail_catalog",
        MODULE / "models" / "catalog.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_six_unique_domains_and_mailboxes():
    catalog = _catalog()
    domains = [p["domain"] for p in catalog.MAIL_PROFILES]
    mailboxes = [p["mailbox"] for p in catalog.MAIL_PROFILES]
    assert len(catalog.MAIL_PROFILES) == 6
    assert len(set(domains)) == 6
    assert len(set(mailboxes)) == 6
    for profile in catalog.MAIL_PROFILES:
        assert profile["mailbox"].endswith("@" + profile["domain"])
        assert profile["mailbox"].startswith("administracion@")


def test_thirty_aliases_stay_on_own_domain():
    catalog = _catalog()
    count = 0
    for profile in catalog.MAIL_PROFILES:
        for role, local in catalog.ROLE_LOCAL.items():
            if role == "admin":
                continue
            addr = catalog.address_for(profile, role)
            count += 1
            assert addr == f"{local}@{profile['domain']}"
            assert catalog.belongs_to_domain(addr, profile["domain"])
            for other in catalog.MAIL_PROFILES:
                if other is profile:
                    continue
                assert not catalog.belongs_to_domain(addr, other["domain"])
    assert count == 30


def test_role_mapping_for_documents():
    catalog = _catalog()
    assert catalog.role_for_model("sale.order") == "sales"
    assert catalog.role_for_model("crm.lead") == "sales"
    assert catalog.role_for_model("purchase.order") == "purchase"
    assert catalog.role_for_model("account.move", "out_invoice") == "invoice"
    assert catalog.role_for_model("account.move", "out_refund") == "invoice"
    assert catalog.role_for_model("account.move", "in_invoice") == "purchase"
    assert catalog.role_for_model("account.payment") == "accounting"
    assert catalog.role_for_model("mail.message") == "admin"
    assert catalog.role_for_model("purchase.order") == catalog.role_for_model(
        "purchase.requisition"
    )


def test_profiles_match_company_names():
    catalog = _catalog()
    assert catalog.profile_for_code("DOR")["domain"] == "inversionesdoralex.com"
    assert catalog.profile_for_company_name("Inversiones Doralex SRL")["code"] == "DOR"
    assert catalog.profile_for_company_name("Piñaria")["domain"] == "pinariagroup.com"
    assert (
        catalog.profile_for_company_name("Dominion Business")["domain"]
        == "dominion-business.com"
    )
    assert catalog.profile_for_company_name("El Mayuma")["domain"] == "elmayuma.com"
    assert (
        catalog.profile_for_company_name("Rempart Group")["domain"]
        == "rempartgroup.com"
    )
    assert catalog.profile_for_company_name("Blue Elite")["domain"] == "blueelite.net"


def test_module_does_not_embed_secrets():
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in MODULE.rglob("*")
        if path.suffix in {".py", ".xml", ".csv"}
    )
    assert "BEGIN PRIVATE KEY" not in text
    assert "BEGIN CERTIFICATE" not in text
    catalog = _catalog()
    assert catalog.all_domains() == (
        "inversionesdoralex.com",
        "pinariagroup.com",
        "dominion-business.com",
        "elmayuma.com",
        "rempartgroup.com",
        "blueelite.net",
    )


def test_graph_send_is_used_instead_of_smtp_for_mapped_domains():
    server = (MODULE / "models" / "ir_mail_server.py").read_text(encoding="utf-8")
    mail = (MODULE / "models" / "mail_mail.py").read_text(encoding="utf-8")
    graph = (MODULE / "models" / "graph_client.py").read_text(encoding="utf-8")
    assert "sendMail" in graph
    assert "Mail.Send" in graph
    assert "all_domains" in server
    assert "_dx_apply_company_from" in mail
    assert "belongs_to_domain" in mail
    assert "self.exists()" in mail
    assert "smtp_password" not in graph
    assert "list_sent" in graph
    assert "sentitems" in graph


def test_outgoing_uses_primary_mailbox_not_role_aliases():
    catalog = _catalog()
    for profile in catalog.MAIL_PROFILES:
        assert profile["mailbox"] == f"administracion@{profile['domain']}"
    company = (MODULE / "models" / "res_company.py").read_text(encoding="utf-8")
    mail = (MODULE / "models" / "mail_mail.py").read_text(encoding="utf-8")
    composer = (MODULE / "models" / "mail_compose_message.py").read_text(
        encoding="utf-8"
    )
    invoice = (MODULE / "models" / "account_move_send.py").read_text(encoding="utf-8")
    thread = (MODULE / "models" / "mail_thread.py").read_text(encoding="utf-8")
    assert "_dx_outgoing_address" in company
    assert "_dx_outgoing_address" in mail
    assert "_dx_outgoing_address" in composer
    assert "_dx_outgoing_address" in invoice
    assert "_dx_outgoing_address" in thread
    assert "ventas@" not in composer
    assert "facturacion@" not in invoice
    assert "_dx_address_for_role" not in mail


def test_composer_and_invoice_force_company_identity():
    composer = (MODULE / "models" / "mail_compose_message.py").read_text(
        encoding="utf-8"
    )
    invoice = (MODULE / "models" / "account_move_send.py").read_text(encoding="utf-8")
    company = (MODULE / "models" / "res_company.py").read_text(encoding="utf-8")
    views = (MODULE / "views" / "mail_send_views.xml").read_text(encoding="utf-8")
    assert "_dx_document_company" in composer
    assert "email_from = addr" in composer
    assert "reply_to = addr" in composer
    assert "move.company_id if move else wizard.company_id" in invoice
    assert '"res_ids"' in composer
    assert '"composition_mode"' in composer
    assert "partner_id" in composer
    assert 'kwargs["email_from"]' in invoice
    assert "dx_email_from" in invoice
    assert "dx_email_from" in views
    assert "all_domains" in company
    assert "alias_domain_id = False" in company
