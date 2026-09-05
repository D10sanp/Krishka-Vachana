"""Shared time helper.

A single utcnow() used across schemas/services instead of the six
near-identical copies that had accumulated (farmer.py, crop.py, slot.py,
queue.py, otp_service.py, and a dead one in centre.py).
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)
