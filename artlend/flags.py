"""Explainable stress flags for a borrower.

Each flag is a (points, reason) pair, so every score can be traced back to
the filings behind it. Flags are prompts for a closer look, not a verdict.
"""

from datetime import date, datetime, timedelta

DISTRESS_STATUSES = {
    "liquidation", "administration", "receivership",
    "voluntary-arrangement", "insolvency-proceedings",
}


def _d(s):
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def stress_flags(profile, charges, officers, today=None):
    today = today or date.today()
    year_ago = today - timedelta(days=365)
    flags = []
    profile = profile or {}

    status = profile.get("company_status", "")
    if status in DISTRESS_STATUSES:
        flags.append((3, f"company status is '{status}'"))
    if profile.get("has_insolvency_history"):
        flags.append((2, "has insolvency history"))
    if (profile.get("accounts") or {}).get("overdue"):
        flags.append((2, "accounts overdue"))
    if (profile.get("confirmation_statement") or {}).get("overdue"):
        flags.append((1, "confirmation statement overdue"))

    # Several open charges or a new loan is normal for a trading dealer, so on
    # their own they aren't stress. They only add a point next to a real flag.
    outstanding = [c for c in charges if c.get("status") == "outstanding"]
    recent = [c for c in charges if (_d(c.get("created_on", "")) or date.min) >= year_ago]
    if flags and len(outstanding) >= 3:
        flags.append((1, f"{len(outstanding)} outstanding charges"))
    if flags and recent:
        flags.append((1, f"{len(recent)} new charge(s) in the last 12 months"))

    resigned = [o for o in officers if (_d(o.get("resigned_on", "")) or date.min) >= year_ago]
    if len(resigned) >= 2:
        flags.append((1, f"{len(resigned)} officer resignations in the last 12 months"))

    return sum(p for p, _ in flags), [r for _, r in flags]
