"""Guarda: copia de runtime Justgroup no toca Prod ni licencia."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "deployment/doralex/scripts"


def test_copy_script_is_readonly_and_isolated() -> None:
    copy = (SCRIPTS / "copy_justgroup_enterprise_runtime.sh").read_text()
    audit = (SCRIPTS / "audit_justgroup_readonly.sh").read_text()
    assert "rsync -a" in copy
    assert "/opt/doralex/enterprise-addons/19" in copy
    assert "web_enterprise" in copy
    assert "JUSTECH_SUBSCRIPTION_COPIED = NO" in copy
    assert (
        "/opt/doralex/enterprise " in copy
        or "NO escribe en /opt/doralex/enterprise" in copy
    )
    assert " -i " not in audit
    assert " -u " not in audit
    assert "systemctl restart" not in audit
    assert "CONFIRM=yes" in copy
    for line in copy.splitlines():
        if "python3 /usr/bin/odoo" in line:
            raise AssertionError("copy no debe invocar odoo")


def test_qweb_inventory_script_targets_staging_only() -> None:
    inv = (SCRIPTS / "inventory_staging_qweb.sh").read_text()
    assert "enterprise-staging" in inv
    assert "justech_alexander" in inv
    assert "doralex-production" not in inv


def test_justgroup_bootstrap_does_not_print_key() -> None:
    boot = (SCRIPTS / "justgroup_ssh_bootstrap.sh").read_text()
    assert "JUSTGROUP_SSH_PRIVATE_KEY" in boot
    assert 'echo "$JUSTGROUP_SSH_PRIVATE_KEY"' not in boot
    assert "justgroup_vps_ed25519" in boot
