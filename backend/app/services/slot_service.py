"""Smart Slot booking business logic.

Capacity is enforced per (centre_id, slot_date, slot_window) via the
repository's create_if_capacity_available - the same atomic
reserve-then-create pattern app/services/farmer_service.py uses for
Aadhaar uniqueness, so two farmers racing for the last slot in a window
can't both succeed (see tests/test_bookings.py's concurrency test).
"""
import logging
import uuid
from datetime import datetime
from typing import List
from zoneinfo import ZoneInfo

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.repositories.base import (
    CentreRepository,
    CropRepository,
    FarmerRepository,
    SlotBookingRepository,
)
from app.schemas.slot import SlotBookingCreate, SlotBookingOut, utcnow

PROCUREMENT_CENTRE_TIMEZONE = ZoneInfo("Asia/Kolkata")

logger = logging.getLogger("app.slot")


def _notify_booking_confirmed(farmer_repo: FarmerRepository, record: dict) -> None:
    """Send a best-effort SMS confirmation without failing the booking.

    This is the Phase 3 SMS integration; see app/core/sms.py.
    """
    try:
        from app.core.config import get_settings
        from app.core.sms import send_sms

        farmer = farmer_repo.get(record["farmer_id"])
        phone_number = farmer.get("phone_number") if farmer else None
        if not phone_number:
            return
        send_sms(
            get_settings(),
            phone_number,
            f"Krishka Vachana: your slot at {record['centre_id']} on {record['slot_date']} "
            f"({record['slot_window']}) is confirmed.",
        )
    except Exception:  # pragma: no cover - notification is best-effort only
        logger.exception("Failed to send booking-confirmation SMS")


def book_slot(
    booking_repo: SlotBookingRepository,
    centre_repo: CentreRepository,
    farmer_repo: FarmerRepository,
    crop_repo: CropRepository,
    farmer_id: str,
    payload: SlotBookingCreate,
) -> SlotBookingOut:
    """Book a slot at a procurement centre with atomic capacity enforcement."""
    if farmer_repo.get(farmer_id) is None:
        raise NotFoundError("Register a farmer profile before booking a slot")

    centre = centre_repo.get(payload.centre_id)
    if centre is None:
        raise NotFoundError("Procurement centre not found")

    if payload.slot_date < datetime.now(PROCUREMENT_CENTRE_TIMEZONE).date():
        raise ValidationAppError("slot_date cannot be in the past")

    if payload.crop_id is not None:
        farmer_crops = crop_repo.list_by_farmer(farmer_id)
        if not any(c["crop_id"] == payload.crop_id for c in farmer_crops):
            raise NotFoundError("crop_id does not belong to a registered crop for this farmer")

    booking_id = str(uuid.uuid4())
    record = booking_repo.create_if_capacity_available(
        booking_id,
        centre["capacity_per_slot"],
        {
            "farmer_id": farmer_id,
            "centre_id": payload.centre_id,
            "slot_date": payload.slot_date,
            "slot_window": payload.slot_window,
            "crop_id": payload.crop_id,
            "notes": payload.notes,
            "status": "booked",
            "created_at": utcnow(),
        },
    )
    if record is None:
        raise ConflictError(
            "This slot is full or you already have an active booking for it"
        )
    # Imported lazily to avoid queue_service's module-level timezone import
    # creating a cycle while these service modules are initialized.
    from app.services.queue_service import dispatch_notification

    dispatch_notification(
        lambda: _notify_booking_confirmed(farmer_repo, record),
        "Booking-confirmation SMS",
    )
    return SlotBookingOut.model_validate(record)


def list_my_bookings(booking_repo: SlotBookingRepository, farmer_id: str) -> List[SlotBookingOut]:
    """List all bookings for a farmer, sorted by date and time (most recent first)."""
    records = booking_repo.list_by_farmer(farmer_id)
    records.sort(key=lambda r: (r["slot_date"], r["slot_window"]), reverse=True)
    return [SlotBookingOut.model_validate(r) for r in records]


def get_my_booking(booking_repo: SlotBookingRepository, farmer_id: str, booking_id: str) -> SlotBookingOut:
    """Get a specific booking owned by a farmer."""
    record = booking_repo.get(booking_id)
    # Booking exists but belongs to someone else: still 404, not 403, so we
    # don't leak whether a given booking_id exists to a farmer who doesn't
    # own it.
    if record is None or record.get("farmer_id") != farmer_id:
        raise NotFoundError("Booking not found")
    return SlotBookingOut.model_validate(record)


def cancel_booking(booking_repo: SlotBookingRepository, farmer_id: str, booking_id: str) -> SlotBookingOut:
    """Cancel a booking owned by a farmer and free its slot capacity."""
    record = booking_repo.cancel(booking_id, farmer_id)
    if record is None:
        raise NotFoundError("Booking not found")
    return SlotBookingOut.model_validate(record)
