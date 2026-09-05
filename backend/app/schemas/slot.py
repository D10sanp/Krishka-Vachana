"""Smart Slot booking schemas.

Covers the "...and Slot booking" half of Phase 2. A booking reserves one
farmer a place in one procurement centre's slot window on one day.
Capacity is enforced per (centre, date, window) - see
app/services/slot_service.py and the repository's
create_if_capacity_available, which uses the same atomic
reserve-then-create pattern app/services/farmer_service.py already uses
for Aadhaar uniqueness.
"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.core.time import utcnow
from app.schemas.centre import SLOT_WINDOWS


class SlotBookingCreate(BaseModel):
    """Schema for creating a Smart Slot booking.

    Note: "slot_date must not be in the past" is a centre-business-timezone
    rule enforced in app/services/slot_service.py.
    """

    centre_id: str = Field(min_length=1)
    slot_date: date = Field(description="Date the farmer intends to arrive (YYYY-MM-DD)")
    slot_window: str = Field(description=f"One of {SLOT_WINDOWS}")
    crop_id: Optional[str] = Field(
        default=None,
        description="Optional link to a previously registered crop (app/schemas/crop.py)",
    )
    notes: Optional[str] = Field(default=None, max_length=280)

    @field_validator("slot_window")
    @classmethod
    def validate_slot_window(cls, v: str) -> str:
        """Validate that slot_window is one of the predefined time windows."""
        if v not in SLOT_WINDOWS:
            raise ValueError(f"slot_window must be one of {SLOT_WINDOWS}")
        return v

class SlotBookingOut(BaseModel):
    """Schema for slot booking responses."""

    booking_id: str
    farmer_id: str
    centre_id: str
    slot_date: date
    slot_window: str
    crop_id: Optional[str] = None
    notes: Optional[str] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
