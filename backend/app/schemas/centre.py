"""Procurement-centre schemas.

Covers the "Procurement-centre selection" half of the Phase 2 feature
"Procurement-centre selection and Slot booking" (see team_work_division.md
and the backend README roadmap). Centre *data* (which centres exist, their
capacity) is reference/master data that will live in Firestore once the
Database & Infrastructure engineer wires that collection up (see
app/repositories/firestore.py) - this module only defines the shape
Backend expects that data to have. The in-memory fallback
(app/repositories/memory.py) seeds a handful of sample centres so this is
usable in dev/tests before that collection exists.
"""
from datetime import datetime

from pydantic import BaseModel, Field

# Fixed daily slot windows every centre operates on. Kept as a shared
# constant (not per-centre) to keep Phase 2 booking logic simple - giving
# each centre its own operating hours is a reasonable Phase 3+ enhancement
# if a real mandi's hours turn out to differ.
SLOT_WINDOWS = [
    "06:00-08:00",
    "08:00-10:00",
    "10:00-12:00",
    "12:00-14:00",
    "14:00-16:00",
    "16:00-18:00",
]


class CentreOut(BaseModel):
    """Schema for procurement centre responses."""

    centre_id: str
    name: str
    village: str
    district: str
    state: str
    capacity_per_slot: int = Field(gt=0, description="Max farmers bookable per slot window")
    created_at: datetime

    model_config = {"from_attributes": True}
