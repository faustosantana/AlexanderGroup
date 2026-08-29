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
    for raw in (convert, waves):
        for line in raw.splitlines():
            if "python3 /usr/bin/odoo" in line:
                assert "-u " not in line
    assert " -i web_enterprise" in convert
    assert "github.com/odoo/enterprise" in fetch
    assert "Justgroup" in fetch
    assert "neutralization" in clone
    assert "doralexgroup.cloud" in clone
    assert "CONFIRM=yes" in clone


def test_lib_accepts_enterprise_staging() -> None:
    lib = (SCRIPTS / "lib.sh").read_text(encoding="utf-8")
    assert "enterprise-staging" in lib


def test_status_doc_blocks_cutover() -> None:
    status = (REPO / "docs/enterprise_conversion/STATUS.md").read_text()
    assert "CUTOVER_ALLOWED = NO" in status
    assert "BLOQUEADO" in status
