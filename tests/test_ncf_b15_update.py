"""Authorized B15 sequence gates and NCF balance alerts (no live consume)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from tools.alexander_ncf_update.authorized import AUTHORIZED_B15, format_ncf
from tools.alexander_ncf_update.gates import (
    classify_balance,
    expected_remaining,
    gate_max_real,
    gate_next_exists,
    gate_range,
    paper_gap,
)

REPO = Path(__file__).resolve().parent.parent
BASE = REPO / "addons" / "alexander" / "justech_alexander_base"


def test_doralex_b15_range():
    spec = AUTHORIZED_B15["DOR"]
    assert spec["ncf_from"] == "B1500000141"
    assert spec["ncf_to"] == "B1500000160"
    assert spec["sequence_start"] == 141
    assert spec["sequence_end"] == 160
    assert not gate_range(spec)


def test_doralex_b15_next_152():
    spec = AUTHORIZED_B15["DOR"]
    assert spec["ncf_next"] == "B1500000152"
    assert spec["next_sequence"] == 152
    assert spec["last_used"] == 151
    assert format_ncf("B15", 152) == "B1500000152"
    assert not gate_max_real(spec, 151)
    assert not paper_gap(spec, 151)
    assert gate_max_real(spec, 153) == ["MAX_REAL_AHEAD_OF_AUTHORIZATION"]


def test_mayuma_b15_range():
    spec = AUTHORIZED_B15["MAY"]
    assert spec["ncf_from"] == "B1500000109"
    assert spec["ncf_to"] == "B1500000118"
    assert not gate_range(spec)


def test_mayuma_b15_next_113():
    spec = AUTHORIZED_B15["MAY"]
    assert spec["ncf_next"] == "B1500000113"
    assert spec["next_sequence"] == 113
    assert expected_remaining("MAY") == 6
    assert not gate_max_real(spec, 112)
    assert paper_gap(spec, 110)
    assert not gate_max_real(spec, 110)


def test_rempart_b15_range():
    spec = AUTHORIZED_B15["REM"]
    assert spec["ncf_from"] == "B1500000106"
    assert spec["ncf_to"] == "B1500000113"
    assert spec["date_to"] == date(2027, 1, 3)
    assert not gate_range(spec)


def test_rempart_b15_next_112():
    spec = AUTHORIZED_B15["REM"]
    assert spec["ncf_next"] == "B1500000112"
    assert spec["next_sequence"] == 112
    assert expected_remaining("REM") == 2
    assert not gate_max_real(spec, 111)
    assert paper_gap(spec, 110)
    assert not gate_max_real(spec, 110)


def test_doralex_b13_blocked():
    alert = (BASE / "models" / "ncf_balance_alert.py").read_text(encoding="utf-8")
    apply = (REPO / "tools" / "alexander_ncf_update" / "apply_ncf.py").read_text(
        encoding="utf-8"
    )
    assert "action_cancel" in apply
    assert "BLOCK_B13" in apply
    assert "consume_next(" not in apply
    assert "next_by_id(" not in apply
    assert "next_by_code(" not in apply
    assert "classify_ncf_balance" in alert


def test_ncf_next_not_consumed_on_read():
    apply = (REPO / "tools" / "alexander_ncf_update" / "apply_ncf.py").read_text(
        encoding="utf-8"
    )
    preview = (BASE / "models" / "ncf_balance_alert.py").read_text(encoding="utf-8")
    assert "next_by_id(" not in apply
    assert "next_by_code(" not in apply
    assert "consume_next(" not in apply
    assert "env.cr.commit()" in apply
    assert "dx_preview_next_ncf" in preview
    assert "without consuming" in preview
    assert not gate_next_exists(AUTHORIZED_B15["DOR"], False)
    assert gate_next_exists(AUTHORIZED_B15["DOR"], True) == ["NEXT_NCF_ALREADY_EXISTS"]


def test_ncf_low_balance_warning():
    today = date(2026, 9, 26)
    assert classify_balance(11, date(2027, 12, 31), today) == "NORMAL"
    assert classify_balance(10, date(2027, 12, 31), today) == "WARNING"
    assert classify_balance(9, date(2027, 12, 31), today) == "WARNING"
    assert classify_balance(6, date(2026, 12, 31), today) == "WARNING"
    assert classify_balance(3, date(2027, 1, 3), today) == "CRITICAL"
    assert classify_balance(2, date(2027, 1, 3), today) == "CRITICAL"
    assert classify_balance(0, date(2027, 12, 31), today) == "EXHAUSTED"
    assert classify_balance(20, date(2025, 12, 31), today) == "EXPIRED"
    assert expected_remaining("DOR") == 9
    assert expected_remaining("MAY") == 6
    assert expected_remaining("REM") == 2


def test_cross_company_authorized_sequences_are_isolated():
    dor = AUTHORIZED_B15["DOR"]
    may = AUTHORIZED_B15["MAY"]
    rem = AUTHORIZED_B15["REM"]
    assert dor["authorization_number"] != may["authorization_number"]
    assert may["authorization_number"] != rem["authorization_number"]
    assert dor["ncf_next"] != may["ncf_next"] != rem["ncf_next"]
    assert {dor["needles"], may["needles"], rem["needles"]} == {
        ("INVERSIONES DORALEX",),
        ("EL MAYUMA",),
        ("REMPART GROUP",),
    }


def test_manifest_has_balance_view_and_version():
    manifest = (BASE / "__manifest__.py").read_text(encoding="utf-8")
    assert "19.0.1.0.21" in manifest
    assert "views/ncf_range_alert_views.xml" in manifest
    xml = (BASE / "views" / "ncf_range_alert_views.xml").read_text(encoding="utf-8")
    assert "dx_ncf_balance_level" in xml
    assert "authorization_number" in xml
