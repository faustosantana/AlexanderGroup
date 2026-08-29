"""Unit tests for customer statement aging and balance invariants."""

import sys
from datetime import date
from pathlib import Path

MATH = (
    Path(__file__).resolve().parent.parent
    / "addons"
    / "alexander"
    / "justech_alexander_reports"
    / "models"
)
if str(MATH) not in sys.path:
    sys.path.insert(0, str(MATH))

from statement_math import (  # noqa: E402
    aging_bucket,
    assert_balance_invariants,
    assert_receivable_invariants,
    classify_open_amount,
    days_status_label,
    residual_after_partials,
)


def test_aging_buckets():
    assert aging_bucket(0) == "current"
    assert aging_bucket(-12) == "current"
    assert aging_bucket(1) == "d30"
    assert aging_bucket(30) == "d30"
    assert aging_bucket(31) == "d60"
    assert aging_bucket(60) == "d60"
    assert aging_bucket(61) == "d90"
    assert aging_bucket(90) == "d90"
    assert aging_bucket(91) == "d90p"


def test_days_labels_never_negative():
    cutoff = date(2026, 8, 28)
    assert days_status_label(date(2026, 8, 18), cutoff) == "Vencido 10"
    assert days_status_label(date(2026, 9, 7), cutoff) == "Por vencer 10"
    assert days_status_label(cutoff, cutoff) == "0"
    assert days_status_label(None, cutoff) == "—"


def test_kpi_equals_overdue_plus_current_and_aging():
    cutoff = date(2026, 8, 28)
    items = [
        (1000.0, date(2026, 7, 1)),  # 58 days overdue -> d60
        (250.0, date(2026, 8, 20)),  # 8 days overdue -> d30
        (400.0, date(2026, 9, 10)),  # current
        (-150.0, date(2026, 8, 1)),  # unapplied credit -> current
    ]
    overdue = current = credits = 0.0
    aging = {"current": 0.0, "d30": 0.0, "d60": 0.0, "d90": 0.0, "d90p": 0.0}
    for amount, due in items:
        ov, cur, bucket, aged, cred = classify_open_amount(amount, due, cutoff)
        overdue += ov
        current += cur
        credits += cred
        if bucket != "credit":
            aging[bucket] += aged
    receivable = overdue + current
    net = receivable + credits
    assert abs(receivable - 1650.0) < 0.01
    assert abs(credits + 150.0) < 0.01
    assert abs(net - 1500.0) < 0.01
    assert_receivable_invariants(receivable, overdue, current, aging, net, credits)


def test_historical_residual_ignores_later_application():
    original = 1000.0
    applied_until_cutoff = 200.0
    assert residual_after_partials(original, applied_until_cutoff) == 800.0
    assert residual_after_partials(-500.0, 200.0) == -300.0


def test_invariants_fail_on_mismatch():
    try:
        assert_balance_invariants(100, 40, 50, {"current": 50, "d30": 40})
    except AssertionError:
        return
    raise AssertionError("expected KPI mismatch")
