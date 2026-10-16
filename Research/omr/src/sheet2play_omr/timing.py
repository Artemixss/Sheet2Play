"""Shared rational reconstruction for corrected evaluation identities."""
from __future__ import annotations

from fractions import Fraction
import math
from typing import Any

DENOMINATOR_LIMIT = 4096


def rational_time(value: Any) -> Fraction:
    """Recover serialized binary64 rationals without quantizing genuine timing errors.

    Exact fractions remain exact. Denominator reconstruction is accepted only within
    binary64 arithmetic roundoff (eight ULPs), never a musical matching tolerance.
    """
    if isinstance(value, bool):
        raise ValueError("Boolean timing is invalid")
    raw = Fraction(str(value))
    if isinstance(value, Fraction) or "/" in str(value):
        return raw
    reconstructed = raw.limit_denominator(DENOMINATOR_LIMIT)
    number = float(raw)
    if not math.isfinite(number):
        raise ValueError("Nonfinite timing is invalid")
    roundoff = Fraction.from_float(8 * math.ulp(number))
    return reconstructed if abs(raw - reconstructed) <= roundoff else raw
