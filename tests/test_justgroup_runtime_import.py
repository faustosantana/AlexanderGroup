"""Import del export Justgroup: hash fijo, sin Prod, sin -u all."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "deployment/doralex/scripts"


def test_export_import_evidence_keeps_reports_and_blocks_core_guess() -> None:
    ev = (
        REPO / "docs/enterprise_conversion/evidence/wave2_export_import_20260829.txt"
    ).read_text()
    assert "EXPORT_FINAL_HASH_MATCH = YES" in ev
    assert "QWEB_BEFORE = 58" in ev
    assert "ALEXANDER_REPORTS_ACTION = PRESERVE_DORALEX" in ev
    assert "CORE_VERSION_MATCH = NO" in ev
    assert "odoo_19.0.20260324_all.deb" in ev
    assert "NO web_enterprise install" in ev
    assert "CUTOVER_ALLOWED = NO" in ev
    table = (
        REPO / "docs/enterprise_conversion/evidence/custom_addons_compare_20260829.tsv"
    ).read_text()
    assert "justech_alexander_reports" in table
    assert "DORALEX_ONLY" in table


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
    assert "enterprise-slim" in apply
    assert (
        "/usr/lib/odoo/enterprise,/usr/lib/odoo/custom-addons -i web_enterprise"
        not in apply
    )
    for line in apply.splitlines():
        if "python3 /usr/bin/odoo" in line:
            assert "-u " not in line
    assert "enterprise-staging" in apply
    assert "production" in apply  # healthcheck only
    assert "CONFIRM=yes" in apply
    assert "justech_alexander_reports" not in apply or "check_staging_reports" in apply


def test_wave3_core_runtime_keeps_reports_and_blocks_cutover() -> None:
    ev = (
        REPO / "docs/enterprise_conversion/evidence/wave3_core_runtime_20260829.txt"
    ).read_text()
    assert "CORE_FINAL_HASH_MATCH = YES" in ev
    assert "CORE_VERSION_MATCH = YES" in ev
    assert "CORE_SECRETS_FOUND = none" in ev
    assert "WEB_ENTERPRISE_INSTALLED = YES" in ev
    assert "ENTERPRISE_UI = PASS" in ev
    assert "QWEB_AFTER = 58" in ev
    assert "QWEB_HASH_MISMATCH_UNEXPECTED = 0" in ev
    assert "CLOSE_TRANSFER_CHANNEL = NO" in ev
    assert "CUTOVER_ALLOWED = NO" in ev
    assert "JUSTGROUP_DATA_COPIED = NO" in ev
    assert "doralex-odoo-enterprise:19.0.20260324" in ev
