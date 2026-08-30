"""Plantillas y scripts de conversión Community → Enterprise (sin Docker)."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STAGING = REPO / "deployment/doralex/enterprise-staging"
SCRIPTS = REPO / "deployment/doralex/scripts"


def test_staging_templates_exist() -> None:
    assert (STAGING / "docker-compose.yml").is_file()
    assert (STAGING / ".env.example").is_file()
    assert (STAGING / "config/odoo.conf.example").is_file()
    assert (STAGING / "enterprise-addons/ENTERPRISE_SOURCE_PENDING").is_file()
    assert (STAGING / "Dockerfile.enterprise").is_file()


def test_derived_image_keeps_odoo19_base() -> None:
    df = (STAGING / "Dockerfile.enterprise").read_text(encoding="utf-8")
    assert "FROM odoo:19" in df
    assert "odoo-enterprise.deb" in df
    assert "allow-downgrades" in df or "force-downgrade" in df
    assert "web_enterprise" in df


def test_staging_isolation_names() -> None:
    compose = (STAGING / "docker-compose.yml").read_text(encoding="utf-8")
    assert "doralex_ent_staging_net" in compose
    assert "doralex_ent_staging_db_data" in compose
    assert "doralex_prod_db_data" not in compose
    assert "doralex_prod_odoo_data" not in compose
    assert "127.0.0.1:${ODOO_HTTP_PORT:-8269}:8069" in compose
    assert "./enterprise-addons" in compose
    assert "../enterprise" not in compose


def test_scripts_forbid_u_all_and_justgroup_copy() -> None:
    convert = (SCRIPTS / "convert_community_to_enterprise.sh").read_text()
    fetch = (SCRIPTS / "fetch_odoo_enterprise.sh").read_text()
    waves = (SCRIPTS / "install_enterprise_waves.sh").read_text()
    clone = (SCRIPTS / "clone_prod_to_enterprise_staging.sh").read_text()
    build = (SCRIPTS / "build_enterprise_staging_image.sh").read_text()
    for raw in (convert, waves):
        for line in raw.splitlines():
            if "python3 /usr/bin/odoo" in line:
                assert "-u " not in line
    assert " -i web_enterprise" in convert
    assert "--stop-after-init" in convert
    assert "doralex-odoo-enterprise:19" in convert
    assert "doralex-odoo-enterprise:19" in build
    assert "production" in convert
    assert "enterprise-staging stop odoo" in convert
    assert "github.com/odoo/enterprise" in fetch
    assert "Justgroup" in fetch
    assert "archive" in fetch
    assert "try_deb" in fetch
    assert "try_official_download" in fetch
    assert "PENDING_OFFICIAL_PACKAGE" in fetch
    assert "AUTOMATIC_DOWNLOAD = BLOCKED" in fetch
    assert "deb_19e" in fetch
    assert "GITHUB_BLOCKER = REMOVE" in fetch
    assert (SCRIPTS / "download_odoo_enterprise.sh").is_file()
    drop_start = fetch.index("print_official_drop_instructions() {")
    drop_end = fetch.index("\n}", drop_start)
    assert "github.com" not in fetch[drop_start:drop_end]
    assert "neutralization" in clone
    assert "doralexgroup.cloud" in clone
    assert "CONFIRM=yes" in clone
    assert "CONFIRM=yes" in convert


def test_fetch_tries_official_package_before_git() -> None:
    fetch = (SCRIPTS / "fetch_odoo_enterprise.sh").read_text()
    assert fetch.index("if try_official_download;") < fetch.index("if try_deb;")
    assert fetch.index("if try_deb;") < fetch.index("if try_git;")
    assert fetch.index("if try_archive;") < fetch.index("if try_git;")


def test_lib_accepts_enterprise_staging() -> None:
    lib = (SCRIPTS / "lib.sh").read_text(encoding="utf-8")
    assert "enterprise-staging" in lib


def test_status_doc_blocks_cutover() -> None:
    status = (REPO / "docs/enterprise_conversion/STATUS.md").read_text()
    assert "CUTOVER_ALLOWED = NO" in status
    assert "GITHUB_BLOCKER = REMOVE" in status
    assert "JUSTECH_SUBSCRIPTION_COPIED = NO" in status
    assert (
        "ENTERPRISE_PACKAGE_ROUTE = OFFICIAL_DEB" in status
        or "ENTERPRISE_PACKAGE_ROUTE = PRIMARY" in status
        or "ENTERPRISE_PACKAGE_ROUTE = JUSTGROUP_RUNTIME_COPY" in status
    )
    assert "CORE_VERSION_MATCH = YES" in status
    assert "ALEXANDER_REPORTS_ACTION = PRESERVE_DORALEX" in status
    assert "TEMP_TRANSFER_ACCESS_CLOSED = YES" in status
    assert "EXPORT_FINAL_HASH_MATCH = YES" in status
    assert "WAIT_EXACT_CORE_PACKAGE" in status
    assert "odoo_19.0.20260324_all.deb" in status
    assert "CLOSE_TRANSFER_CHANNEL = YES" in status
    assert "TRANSFER_CHANNEL_CLOSED = YES" in status
    assert "WEB_ENTERPRISE_INSTALLED = YES" in status
    assert "CUSTOM_COMMON_MISSING = 0" in status
    assert "FISCAL_ENGINE_INSTALLED = YES" in status
    assert "CUTOVER_ALLOWED = NO" in status


def test_wave4_custom_stack_evidence_blocks_cutover() -> None:
    ev = (
        REPO / "docs/enterprise_conversion/evidence/"
        "wave4_justech_custom_stack_20260829.txt"
    ).read_text(encoding="utf-8")
    assert "TRANSFER_CHANNEL_CLOSED = YES" in ev
    assert "CUSTOM_COMMON_MISSING = 0" in ev
    assert "CUSTOM_COMMON_VERSION_MISMATCH = 0" in ev
    assert "FISCAL_ENGINE_INSTALLED = YES" in ev
    assert "QWEB_AFTER = 58" in ev
    assert "QWEB_HASH_MISMATCH_UNEXPECTED = 0" in ev
    assert "SECRETS_FOUND = none" in ev
    assert "DORALEX_PROD_TOUCHED = NO" in ev
    assert "CUTOVER_ALLOWED = NO" in ev
    assert "JUSTGROUP_DATA_COPIED = NO" in ev


def test_wave5_final_functional_qa_blocks_cutover() -> None:
    ev = (
        REPO / "docs/enterprise_conversion/evidence/"
        "wave5_final_functional_qa_20260830.txt"
    ).read_text(encoding="utf-8")
    status = (REPO / "docs/enterprise_conversion/STATUS.md").read_text()
    assert "FINAL_QA_BACKUP = PASS" in ev
    assert "MARGIN_CONTROL_QA = PASS" in ev
    assert "APPROVAL_QA = PASS" in ev
    assert "AUDIT_QA = PASS" in ev
    assert "QWEB_AFTER = 58" in ev
    assert "QWEB_HASH_MISMATCH_UNEXPECTED = 0" in ev
    assert "CRITICAL_ERRORS = 0" in ev
    assert "HIGH_ERRORS = 0" in ev
    assert "SECRETS_FOUND = none" in ev
    assert "DORALEX_PROD_TOUCHED = NO" in ev
    assert "CUTOVER_ALLOWED = NO" in ev
    assert "READY_FOR_CUTOVER_REVIEW = NO" in ev
    assert "ENTERPRISE_APPS_QA = FAIL" in ev
    assert "DORALEX_SUBSCRIPTION_ACTIVATION = PENDING" in ev
    assert "READY_FOR_CUTOVER_REVIEW = NO" in status
    assert "CUTOVER_ALLOWED = NO" in status
