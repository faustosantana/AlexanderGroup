#!/usr/bin/env python3
"""Compare Justgroup (source of truth) vs Doralex stack manifests.

Does not connect to Justgroup with write credentials. Live version probes use
the public JSON-RPC common.version endpoint only. Default mode is offline
against frozen manifests under docs/stack_audit/.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JG = REPO_ROOT / "docs/stack_audit/justgroup_reference.json"
DEFAULT_DX = REPO_ROOT / "docs/stack_audit/doralex_live_inventory.json"

SAME = "SAME"
MISSING = "MISSING"
DIFFERENT_VERSION = "DIFFERENT_VERSION"
EXTRA = "EXTRA"
UNINSTALLABLE = "UNINSTALLABLE"
UNKNOWN = "UNKNOWN"

DORALEX_IDENTITY_PREFIX = "justech_alexander_"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def edition_of(server_version: str, version_info: list[Any] | None = None) -> str:
    if version_info and len(version_info) >= 6 and version_info[5] == "e":
        return "enterprise"
    if "+e" in (server_version or ""):
        return "enterprise"
    return "community"


def fetch_version(url: str, timeout: float = 20.0) -> dict[str, Any]:
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {"service": "common", "method": "version", "args": []},
            "id": 1,
        }
    ).encode()
    req = urllib.request.Request(
        url.rstrip("/") + "/jsonrpc",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = json.loads(response.read().decode())
    result = body.get("result") or {}
    return {
        "server_version": result.get("server_version"),
        "server_version_info": result.get("server_version_info"),
        "edition": edition_of(
            result.get("server_version") or "", result.get("server_version_info")
        ),
    }


def dx_index(doralex: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["name"]: row for row in doralex.get("installed") or []}


def compare_custom(
    justgroup: dict[str, Any], doralex: dict[str, Any]
) -> list[dict[str, Any]]:
    installed = dx_index(doralex)
    rows: list[dict[str, Any]] = []
    for mod in justgroup.get("custom_modules") or []:
        name = mod["name"]
        if mod.get("doralex_action") == "NOT_APPLICABLE":
            status = SAME if name in installed else "NOT_APPLICABLE"
            rows.append(
                {
                    "module": name,
                    "justgroup_version": mod.get("installed_version"),
                    "doralex_version": (installed.get(name) or {}).get("version"),
                    "status": status,
                    "note": "Justech-product specific; do not copy identity",
                }
            )
            continue
        if name not in installed:
            rows.append(
                {
                    "module": name,
                    "justgroup_version": mod.get("installed_version"),
                    "doralex_version": None,
                    "status": MISSING,
                    "note": "enterprise_dep" if mod.get("enterprise_dep") else "",
                }
            )
            continue
        dx_ver = installed[name].get("version")
        status = SAME if dx_ver == mod.get("installed_version") else DIFFERENT_VERSION
        rows.append(
            {
                "module": name,
                "justgroup_version": mod.get("installed_version"),
                "doralex_version": dx_ver,
                "status": status,
                "note": "",
            }
        )
    return rows


def compare_enterprise_apps(
    justgroup: dict[str, Any], doralex: dict[str, Any]
) -> list[dict[str, Any]]:
    installed = dx_index(doralex)
    wanted_states = {row["name"]: row for row in doralex.get("wanted_states") or []}
    absent = set(doralex.get("wanted_absent") or [])
    rows: list[dict[str, Any]] = []
    for name in justgroup.get("enterprise_apps_required_for_ux_match") or []:
        if name in installed:
            rows.append({"module": name, "status": SAME, "doralex_state": "installed"})
            continue
        state = (wanted_states.get(name) or {}).get("state")
        if name in absent or state is None:
            rows.append(
                {
                    "module": name,
                    "status": UNINSTALLABLE,
                    "doralex_state": "absent_from_community_image",
                }
            )
        elif state == "uninstallable":
            rows.append(
                {
                    "module": name,
                    "status": UNINSTALLABLE,
                    "doralex_state": state,
                }
            )
        else:
            rows.append({"module": name, "status": MISSING, "doralex_state": state})
    return rows


def compare_community_apps(
    justgroup: dict[str, Any], doralex: dict[str, Any]
) -> list[dict[str, Any]]:
    installed = dx_index(doralex)
    wanted_states = {row["name"]: row for row in doralex.get("wanted_states") or []}
    rows: list[dict[str, Any]] = []
    for name in justgroup.get("community_apps_observed_in_justgroup_ux") or []:
        if name in installed:
            rows.append({"module": name, "status": SAME, "doralex_state": "installed"})
            continue
        state = (wanted_states.get(name) or {}).get("state") or "unknown"
        rows.append({"module": name, "status": MISSING, "doralex_state": state})
    return rows


def doralex_extras(doralex: dict[str, Any], justgroup: dict[str, Any]) -> list[str]:
    jg_custom = {m["name"] for m in justgroup.get("custom_modules") or []}
    extras: list[str] = []
    for row in doralex.get("installed") or []:
        name = row["name"]
        if name.startswith(DORALEX_IDENTITY_PREFIX):
            extras.append(name)
        elif name.startswith("justech_") and name not in jg_custom:
            extras.append(name)
    return extras


def spanish_ui_pass(doralex: dict[str, Any]) -> bool:
    langs = doralex.get("langs") or []
    active = {row["code"] for row in langs if row.get("active")}
    if not any(code.startswith("es_") or code == "es" for code in active):
        return False
    user_langs = {row.get("lang") for row in doralex.get("user_langs") or []}
    return bool(user_langs) and all(
        (lang or "").startswith("es") for lang in user_langs if lang
    )


def build_report(
    justgroup: dict[str, Any],
    doralex: dict[str, Any],
    live: dict[str, Any] | None = None,
) -> dict[str, Any]:
    jg_version = (live or {}).get("justgroup", {}).get("server_version") or (
        justgroup.get("odoo") or {}
    ).get("server_version")
    dx_version = (live or {}).get("doralex", {}).get("server_version")
    if not dx_version:
        dx_version = "19.0-20260817"
    jg_edition = edition_of(
        jg_version or "",
        (live or {}).get("justgroup", {}).get("server_version_info"),
    )
    dx_edition = edition_of(
        dx_version or "",
        (live or {}).get("doralex", {}).get("server_version_info"),
    )
    if not live:
        jg_edition = (justgroup.get("odoo") or {}).get("edition") or jg_edition

    custom_rows = compare_custom(justgroup, doralex)
    ent_rows = compare_enterprise_apps(justgroup, doralex)
    comm_rows = compare_community_apps(justgroup, doralex)
    extras = doralex_extras(doralex, justgroup)

    missing_custom = [
        r
        for r in custom_rows
        if r["status"] == MISSING and r.get("note") != "Justech-product specific"
    ]
    version_mismatch = [r for r in custom_rows if r["status"] == DIFFERENT_VERSION]
    missing_ent = [r for r in ent_rows if r["status"] != SAME]
    missing_comm = [r for r in comm_rows if r["status"] != SAME]

    jg_count = (justgroup.get("counts") or {}).get("installed")
    dx_count = doralex.get("installed_count")
    qweb = doralex.get("qweb_doralex") or []
    reports_preserved = bool(qweb) and any(
        (v.get("xml_id") or "").startswith("justech_alexander_reports") for v in qweb
    )

    flags = {
        "ODOO_VERSION_MATCH": jg_version == dx_version,
        "ODOO_EDITION_MATCH": jg_edition == dx_edition == "enterprise",
        "MODULE_SET_MATCH": jg_count == dx_count
        and not missing_ent
        and not missing_comm,
        "MODULE_VERSION_MATCH": not version_mismatch,
        "CUSTOM_MODULES_MATCH": not missing_custom,
        "DEPENDENCIES_MATCH": not missing_ent,
        "FUNCTIONAL_ARCHITECTURE_MATCH": False,
        "MENUS_MATCH": False,
        "QWEB_INFRASTRUCTURE_MATCH": False,
        "DORALEX_REPORTS_PRESERVED": reports_preserved,
        "SPANISH_UI": spanish_ui_pass(doralex),
        "JUSTGROUP_TRANSACTIONS_COPIED": False,
        "JUSTGROUP_PRODUCTION_TOUCHED": False,
        "DORALEX_OPERATIONAL_DATA_CLEAN": False,
        "QA_COMPLETE": False,
        "CUTOVER_ALLOWED": False,
        "FULL_JUSTGROUP_MODULE_LIST": bool(justgroup.get("full_module_list_complete")),
    }

    return {
        "justgroup_odoo": jg_version,
        "doralex_odoo": dx_version,
        "justgroup_edition": jg_edition,
        "doralex_edition": dx_edition,
        "justgroup_installed": jg_count,
        "doralex_installed": dx_count,
        "missing_custom": missing_custom,
        "version_mismatch": version_mismatch,
        "missing_enterprise": missing_ent,
        "missing_community": missing_comm,
        "doralex_identity_extras": extras,
        "custom_rows": custom_rows,
        "flags": flags,
        "live": live or {},
    }


def render_text(report: dict[str, Any]) -> str:
    flags = report["flags"]

    def yn(key: str) -> str:
        return "YES" if flags[key] else "NO"

    def gate(ok: bool) -> str:
        return "PASS" if ok else "FAIL"

    lines = [
        "JUSTGROUP vs DORALEX — stack compare",
        "",
        f"Odoo version:",
        f"  JUSTGROUP = {report['justgroup_odoo']}",
        f"  DORALEX   = {report['doralex_odoo']}",
        f"  {gate(flags['ODOO_VERSION_MATCH'])}",
        "",
        f"Edition:",
        f"  JUSTGROUP = {report['justgroup_edition']}",
        f"  DORALEX   = {report['doralex_edition']}",
        f"  {gate(flags['ODOO_EDITION_MATCH'])}",
        "",
        f"Installed modules:",
        f"  JUSTGROUP = {report['justgroup_installed']}",
        f"  DORALEX   = {report['doralex_installed']}",
        f"  Missing custom = {len(report['missing_custom'])}",
        f"  Version mismatch = {len(report['version_mismatch'])}",
        f"  Missing Enterprise apps = {len(report['missing_enterprise'])}",
        f"  Missing Community apps (UX set) = {len(report['missing_community'])}",
        f"  Doralex identity extras = {len(report['doralex_identity_extras'])}",
        "",
        "Custom modules:",
        f"  {gate(flags['CUSTOM_MODULES_MATCH'])}",
        "QWeb reports (Doralex identity):",
        f"  {gate(flags['DORALEX_REPORTS_PRESERVED'])}",
        "Languages / Spanish UI:",
        f"  {gate(flags['SPANISH_UI'])}",
        "Critical configuration:",
        f"  {gate(flags['ODOO_VERSION_MATCH'] and flags['ODOO_EDITION_MATCH'])}",
        "",
        "Acceptance:",
    ]
    for key in [
        "ODOO_VERSION_MATCH",
        "ODOO_EDITION_MATCH",
        "MODULE_SET_MATCH",
        "MODULE_VERSION_MATCH",
        "CUSTOM_MODULES_MATCH",
        "DEPENDENCIES_MATCH",
        "FUNCTIONAL_ARCHITECTURE_MATCH",
        "MENUS_MATCH",
        "QWEB_INFRASTRUCTURE_MATCH",
        "DORALEX_REPORTS_PRESERVED",
        "SPANISH_UI",
        "JUSTGROUP_TRANSACTIONS_COPIED",
        "JUSTGROUP_PRODUCTION_TOUCHED",
        "DORALEX_OPERATIONAL_DATA_CLEAN",
        "QA_COMPLETE",
        "CUTOVER_ALLOWED",
        "FULL_JUSTGROUP_MODULE_LIST",
    ]:
        lines.append(f"  {key} = {yn(key)}")
    lines.append("")
    lines.append("Missing custom:")
    for row in report["missing_custom"]:
        note = f" ({row['note']})" if row.get("note") else ""
        lines.append(f"  - {row['module']}  JG={row['justgroup_version']}{note}")
    if report["version_mismatch"]:
        lines.append("Version mismatch:")
        for row in report["version_mismatch"]:
            lines.append(
                f"  - {row['module']}  JG={row['justgroup_version']} "
                f"DX={row['doralex_version']}"
            )
    lines.append("Missing Enterprise:")
    for row in report["missing_enterprise"]:
        lines.append(f"  - {row['module']}  {row['status']} ({row['doralex_state']})")
    lines.append("Missing Community (UX set):")
    for row in report["missing_community"]:
        lines.append(f"  - {row['module']}  {row['doralex_state']}")
    lines.append("Doralex identity extras (keep; not Justgroup copies):")
    for name in report["doralex_identity_extras"]:
        lines.append(f"  - {name}")
    lines.append("")
    clone_ok = (
        flags["ODOO_VERSION_MATCH"]
        and flags["ODOO_EDITION_MATCH"]
        and flags["MODULE_SET_MATCH"]
        and flags["CUSTOM_MODULES_MATCH"]
        and flags["SPANISH_UI"]
        and flags["DORALEX_REPORTS_PRESERVED"]
    )
    lines.append(f"DORALEX_CLONE_STATUS = {'APPROVED' if clone_ok else 'REJECTED'}")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--justgroup", type=Path, default=DEFAULT_JG)
    parser.add_argument("--doralex", type=Path, default=DEFAULT_DX)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Probe public common.version on justgroup.app and doralexgroup.cloud",
    )
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    justgroup = load_json(args.justgroup)
    doralex = load_json(args.doralex)
    live = None
    if args.live:
        try:
            live = {
                "justgroup": fetch_version("https://justgroup.app"),
                "doralex": fetch_version("https://doralexgroup.cloud"),
            }
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"LIVE_VERSION_PROBE = FAIL ({exc})", file=sys.stderr)
            return 2
    report = build_report(justgroup, doralex, live)
    text = render_text(report)
    sys.stdout.write(text)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    clone_ok = "DORALEX_CLONE_STATUS = APPROVED" in text
    return 0 if clone_ok else 1


if __name__ == "__main__":
    sys.exit(main())
