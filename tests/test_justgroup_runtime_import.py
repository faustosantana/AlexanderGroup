"""Import del export Justgroup: hash fijo, sin Prod, sin -u all."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "deployment/doralex/scripts"


def test_expected_sha256_and_isolated_extract() -> None:
    xfer = (SCRIPTS / "transfer_justgroup_runtime_export.sh").read_text()
    imp = (SCRIPTS / "import_justgroup_runtime_export.sh").read_text()
    assert "d406ccfd73225db88b83dfd07def618b2c48e1b1aeaebcc5877f76fa26b4cb86" in xfer
    assert "d406ccfd73225db88b83dfd07def618b2c48e1b1aeaebcc5877f76fa26b4cb86" in imp
    assert "rsync -a" in xfer
    assert "runtime-source/19.0-e-20260324" in imp
    assert "/usr/lib/odoo" in imp  # only as forbidden dest / check
    assert "STOP" in imp
    assert "EXPORT_SECRETS_FOUND" in imp


def test_build_image_not_mutable_odoo19() -> None:
    build = (SCRIPTS / "build_doralex_enterprise_image.sh").read_text()
    assert "doralex-odoo-enterprise:19.0.20260324" in build
    assert (
        "odoo:19 latest" in build
        or "no odoo:19 latest" in build.lower()
        or "No usaré odoo:19 latest" in build
    )
    assert "justech_alexander_reports" in build


def test_apply_only_web_enterprise_on_staging() -> None:
    apply = (SCRIPTS / "apply_enterprise_runtime_staging.sh").read_text()
    assert " -i web_enterprise" in apply
    assert "--stop-after-init" in apply
    for line in apply.splitlines():
        if "python3 /usr/bin/odoo" in line:
            assert "-u " not in line
    assert "enterprise-staging" in apply
    assert "production" in apply  # healthcheck only
    assert "CONFIRM=yes" in apply
    assert "justech_alexander_reports" not in apply or "check_staging_reports" in apply
