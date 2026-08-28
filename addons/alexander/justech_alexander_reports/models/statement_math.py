"""Pure helpers for customer statement aging and invariants.

Kept independent of the Odoo registry so unit tests can run without a server.
"""

from __future__ import annotations


def days_overdue(due, cutoff):
    """Return signed day delta: positive = overdue, negative = not yet due."""
    if not due or not cutoff:
        return 0
    return (cutoff - due).days


def days_status_label(due, cutoff):
    """Human label without confusing negatives."""
    if not due or not cutoff:
        return "—"
    delta = days_overdue(due, cutoff)
    if delta > 0:
        return "Vencido %d" % delta
    if delta < 0:
        return "Por vencer %d" % abs(delta)
    return "0"


def aging_bucket(days_past_due):
    """Map overdue days to statement buckets.

    Current: not overdue (0 or negative).
    Then 1–30, 31–60, 61–90, 90+.
    """
    days = int(days_past_due or 0)
    if days <= 0:
        return "current"
    if days <= 30:
        return "d30"
    if days <= 60:
        return "d60"
    if days <= 90:
        return "d90"
    return "d90p"


def classify_open_amount(amount, due, cutoff):
    """Split one open residual into overdue/current and an aging key."""
    residual = float(amount or 0.0)
    if abs(residual) < 0.00001:
        return 0.0, 0.0, "current", 0.0
    if residual < 0:
        # Unapplied credit / payment: keep in current so totals still square.
        return 0.0, residual, "current", residual
    delta = days_overdue(due, cutoff) if due else 0
    overdue_days = delta if delta > 0 else 0
    bucket = aging_bucket(overdue_days)
    if bucket == "current":
        return 0.0, residual, bucket, residual
    return residual, 0.0, bucket, residual


def assert_balance_invariants(total, overdue, current, aging):
    """Raise AssertionError if KPI / aging math does not square."""
    total = float(total or 0.0)
    overdue = float(overdue or 0.0)
    current = float(current or 0.0)
    aging = aging or {}
    age_sum = sum(
        float(aging.get(key) or 0.0) for key in ("current", "d30", "d60", "d90", "d90p")
    )
    if abs(total - (overdue + current)) >= 0.01:
        raise AssertionError(
            "statement KPI mismatch: total=%.4f overdue=%.4f current=%.4f"
            % (total, overdue, current)
        )
    if abs(total - age_sum) >= 0.01:
        raise AssertionError(
            "statement aging mismatch: total=%.4f aging_sum=%.4f buckets=%s"
            % (total, age_sum, aging)
        )
    return True


def residual_after_partials(original, applied):
    """Signed residual after applying positive absolute partials."""
    original = float(original or 0.0)
    applied = abs(float(applied or 0.0))
    if original >= 0:
        return original - applied
    return original + applied
