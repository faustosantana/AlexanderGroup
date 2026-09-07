"""La auditoría de Mailcow queda documentada y sin secretos."""

from pathlib import Path

ROOT = Path("docs/mail_server")
REQUIRED = {
    "00_scorecard.txt",
    "architecture.md",
    "dns_records.md",
    "ports.md",
    "odoo_integration.md",
    "mailboxes.md",
    "backup_restore.md",
    "operations.md",
    "security.md",
}


def test_mail_server_docs_exist_and_record_fail_gate():
    names = {p.name for p in ROOT.iterdir() if p.is_file()}
    assert REQUIRED <= names
    score = (ROOT / "00_scorecard.txt").read_text(encoding="utf-8")
    assert "MAILCOW_RESOURCE_STATUS = FAIL" in score
    assert "FINAL_MAIL_SERVER_STATUS = NOT_INSTALLED" in score
    assert "CORPORATE_MX_TOUCHED = NO" in score
    assert "SMTP25_OUTBOUND = PASS" in score


def test_mail_server_docs_have_no_secrets():
    banned = ("BEGIN PRIVATE", "db_password", "AKIA", "eyJ")
    for path in ROOT.glob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, path
