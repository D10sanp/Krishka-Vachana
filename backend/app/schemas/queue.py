"""Dynamic Queue system schemas.

Covers the Phase 3 "Dynamic Queue system" and "Printable issued token"
features (see backend README roadmap). A Smart Slot booking (Phase 2,
app/schemas/slot.py) reserves capacity ahead of time; checking in here
represents the farmer's *actual, live* arrival-order position at the
centre on the day of their slot - the two are deliberately decoupled so
walk-in/arrival-order queueing doesn't require re-deriving slot capacity
logic.

There is no separate "centre staff" role in this system yet (see
team_work_division.md - only Frontend/Backend/Infra/AI-ML roles exist), so
every status transition below is farmer-initiated and ownership-checked,
mirroring how app/services/slot_service.py's cancel_booking works: a
farmer checks themselves in, and later marks their own entry "served"
(procurement complete) or "left" (leaving without being served) rather
than a centre operator doing it on their behalf. A dedicated operator-
facing flow is a natural future phase once that role/app surface exists.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.core.time import utcnow

QUEUE_STATUSES = ["waiting", "served", "left"]

# Simple fixed heuristic for estimated wait - same spirit as the fixed
# congestion thresholds in app/services/congestion_service.py, not a real
# per-centre throughput measurement. A reasonable MVP estimate.
AVERAGE_SERVICE_MINUTES = 5


class QueueCheckInCreate(BaseModel):
    """Schema for checking in to a procurement centre's live queue."""

    booking_id: str = Field(min_length=1, description="An active Smart Slot booking to check in for")


class QueueEntryOut(BaseModel):
    """Schema for queue entry responses, including live position."""

    queue_id: str
    booking_id: str
    farmer_id: str
    centre_id: str
    sequence_number: int
    token_number: str
    status: str
    joined_at: datetime
    resolved_at: Optional[datetime] = None
    position: Optional[int] = Field(
        default=None, description="1-based live position among waiting entries; null once resolved"
    )
    people_ahead: Optional[int] = None
    estimated_wait_minutes: Optional[int] = None

    model_config = {"from_attributes": True}


class QueueCentreStatusOut(BaseModel):
    """Aggregate, identity-free live queue status for a centre."""

    centre_id: str
    waiting_count: int
    estimated_wait_minutes: int
