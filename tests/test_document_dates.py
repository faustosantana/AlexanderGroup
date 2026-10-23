"""Printed dates stay day/month/year on every Doralex document."""

from __future__ import annotations

import ast
import sys
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / "addons" / "alexander" / "justech_alexander_reports"
MODELS = REPORTS / "models"
if str(MODELS) not in sys.path:
    sys.path.insert(0, str(MODELS))

from datefmt import DX_DATE_FMT, dx_format_date  # noqa: E402


def test_dx_format_date_is_day_month_year() -> None:
    assert DX_DATE_FMT == "%d/%m/%Y"
    assert dx_format_date(date(2027, 12, 31)) == "31/12/2027"
    assert dx_format_date(datetime(2026, 10, 21, 15, 30)) == "21/10/2026"
    assert dx_format_date("2026-10-16") == "16/10/2026"
    assert dx_format_date(False) == "—"
    assert dx_format_date(None) == "—"
    assert dx_format_date("") == "—"
    assert dx_format_date(date(2027, 12, 31)) != "12/31/2027"


def test_compose_and_header_use_dx_format_date() -> None:
    compose = (MODELS / "report_compose.py").read_text(encoding="utf-8")
    company = (MODELS / "res_company.py").read_text(encoding="utf-8")
    partner = (MODELS / "res_partner.py").read_text(encoding="utf-8")
    preview = (MODELS / "preview.py").read_text(encoding="utf-8")
    assert "from .datefmt import dx_format_date" in compose
    assert "return dx_format_date(value)" in compose
    assert "format_date(env, value)" not in compose
    assert "from .datefmt import dx_format_date" in company
    assert "return dx_format_date(value)" in company
    assert "format_date(self.env, value)" not in company
    assert "dx_format_date(date)" in partner
    assert "dx_format_date(due)" in partner
    assert "dx_format_date(cutoff)" in partner
    assert "dx_format_date(fields.Date.context_today(self))" in preview


def test_warranty_prints_strftime_dmy() -> None:
    xml = (REPORTS / "reports" / "warranty_report.xml").read_text(encoding="utf-8")
    assert "strftime('%d/%m/%Y')" in xml
    assert 't-field="doc.date_start"' not in xml


def test_active_langs_forced_to_dmy() -> None:
    report = (MODELS / "ir_actions_report.py").read_text(encoding="utf-8")
    hooks = (REPORTS / "hooks.py").read_text(encoding="utf-8")
    assert "def _dx_force_dmy_date_format" in report
    assert 'date_format != "%d/%m/%Y"' in report
    assert "_dx_force_dmy_date_format()" in report
    assert "_dx_force_dmy_date_format()" in hooks


def test_manifest_version_for_dmy_dates() -> None:
    manifest = (REPORTS / "__manifest__.py").read_text(encoding="utf-8")
    assert "19.0.3.13.11" in manifest
    init = (MODELS / "__init__.py").read_text(encoding="utf-8")
    assert "from . import datefmt" in init
    ast.parse(init)
