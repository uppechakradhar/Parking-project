"""
billing_service.py
Parking duration & tiered hourly billing calculator.
"""
import math
from datetime import datetime


def compute_duration(entry_time: datetime, exit_time: datetime = None):
    """
    Returns a dict with total elapsed time broken into days/hours/minutes/seconds,
    plus total_minutes (float) and a formatted hh:mm:ss string.
    If exit_time is None, uses current UTC time (live timer).
    """
    if exit_time is None:
        exit_time = datetime.utcnow()

    delta = exit_time - entry_time
    total_seconds = max(0, int(delta.total_seconds()))

    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    total_minutes = total_seconds / 60.0
    hh = days * 24 + hours

    return {
        "days": days,
        "hours": hours,
        "minutes": minutes,
        "seconds": seconds,
        "total_seconds": total_seconds,
        "total_minutes": round(total_minutes, 2),
        "formatted": f"{hh:02d}h {minutes:02d}m {seconds:02d}s",
    }


def calculate_bill(entry_time: datetime, exit_time: datetime, pricing_rule):
    """
    Calculate the total bill given entry/exit timestamps and a PricingRule object
    (or dict with base_rate, base_hours, hourly_rate, grace_period_mins).

    Rules:
      - duration <= grace_period_mins  -> fee = 0.00
      - duration <= base_hours (in minutes) -> fee = base_rate
      - duration > base_hours -> fee = base_rate + ceil(extra_hours) * hourly_rate
    """
    if isinstance(pricing_rule, dict):
        base_rate = pricing_rule["base_rate"]
        base_hours = pricing_rule["base_hours"]
        hourly_rate = pricing_rule["hourly_rate"]
        grace_period_mins = pricing_rule["grace_period_mins"]
    else:
        base_rate = pricing_rule.base_rate
        base_hours = pricing_rule.base_hours
        hourly_rate = pricing_rule.hourly_rate
        grace_period_mins = pricing_rule.grace_period_mins

    duration = compute_duration(entry_time, exit_time)
    total_minutes = duration["total_minutes"]
    base_minutes = base_hours * 60

    if total_minutes <= grace_period_mins:
        amount = 0.0
    elif total_minutes <= base_minutes:
        amount = base_rate
    else:
        extra_minutes = total_minutes - base_minutes
        extra_hours = math.ceil(extra_minutes / 60.0)
        amount = base_rate + (extra_hours * hourly_rate)

    return {
        "duration": duration,
        "duration_minutes": int(round(total_minutes)),
        "amount": round(amount, 2),
        "breakdown": {
            "base_rate": base_rate,
            "base_hours": base_hours,
            "hourly_rate": hourly_rate,
            "grace_period_mins": grace_period_mins,
            "extra_hours_charged": max(0, math.ceil((total_minutes - base_minutes) / 60.0)) if total_minutes > base_minutes else 0,
        },
    }


def live_estimate(entry_time: datetime, pricing_rule):
    """Real-time live estimate for a currently parked vehicle (exit_time = now)."""
    return calculate_bill(entry_time, datetime.utcnow(), pricing_rule)
