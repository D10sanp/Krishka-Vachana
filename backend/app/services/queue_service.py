"""Dynamic Queue system business logic (see app/schemas/queue.py)."""
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date as date_type
from datetime import datetime
from threading import BoundedSemaphore
from typing import Callable

from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.core.sms import send_sms
from app.repositories.base import CentreRepository, FarmerRepository, QueueRepository, SlotBookingRepository
from app.schemas.queue import AVERAGE_SERVICE_MINUTES, QueueCentreStatusOut, QueueCheckInCreate, QueueEntryOut, utcnow
from app.services.slot_service import PROCUREMENT_CENTRE_TIMEZONE

logger = logging.getLogger("app.queue")
_notification_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="queue-sms")
_notification_slots = BoundedSemaphore(16)


def dispatch_notification(notification: Callable[[], None], description: str) -> None:
    """Submit a best-effort notification to the bounded worker pool."""
    if not _notification_slots.acquire(blocking=False):
        logger.warning("%s skipped: worker queue is full", description)
        return

    def notify_and_release() -> None:
        """Run the notification and always release its worker-queue slot."""
        try:
            notification()
        except Exception:  # pragma: no cover - notification callbacks are best-effort
            logger.exception("%s failed", description)
        finally:
            _notification_slots.release()

    try:
        _notification_executor.submit(notify_and_release)
    except RuntimeError:  # pragma: no cover - only during interpreter shutdown
        _notification_slots.release()
        logger.warning("%s worker is unavailable", description)


def _to_out(repo: QueueRepository, record: dict) -> QueueEntryOut:
    """Convert a queue entry record to output schema with computed position and wait fields."""
    out = dict(record)
    out["token_number"] = f"{record['sequence_number']:03d}"
    if record.get("status") == "waiting":
        ahead = repo.count_waiting_ahead(
            record["centre_id"], record["queue_date"], record["sequence_number"]
        )
        out["people_ahead"] = ahead
        out["position"] = ahead + 1
        out["estimated_wait_minutes"] = ahead * AVERAGE_SERVICE_MINUTES
    else:
        out["people_ahead"] = None
        out["position"] = None
        out["estimated_wait_minutes"] = None
    return QueueEntryOut.model_validate(out)


def _queue_date_at(instant: datetime) -> str:
    """Return the queue date for an instant in the procurement-centre timezone."""
    return instant.astimezone(PROCUREMENT_CENTRE_TIMEZONE).date().isoformat()


def _notify_check_in(farmer_repo: FarmerRepository, record: dict) -> None:
    """Send best-effort SMS notification with token number to the checked-in farmer."""
    try:
        farmer = farmer_repo.get(record["farmer_id"])
        phone_number = farmer.get("phone_number") if farmer else None
        if not phone_number:
            return
        send_sms(
            get_settings(),
            phone_number,
            f"Krishka Vachana: you're checked in, token #{record['sequence_number']:03d}. "
            "We'll see you soon at the centre.",
        )
    except Exception:  # pragma: no cover - notification is best-effort only
        logger.exception("Failed to send check-in SMS")


def _dispatch_check_in_notification(farmer_repo: FarmerRepository, record: dict) -> None:
    """Dispatch check-in SMS notification to background worker pool without blocking."""
    dispatch_notification(
        lambda: _notify_check_in(farmer_repo, record),
        "Check-in SMS",
    )


def check_in(
    queue_repo: QueueRepository,
    booking_repo: SlotBookingRepository,
    farmer_repo: FarmerRepository,
    farmer_id: str,
    payload: QueueCheckInCreate,
) -> QueueEntryOut:
    """Check the farmer in to their booked centre's live queue."""
    booking = booking_repo.get(payload.booking_id)
    if booking is None or booking.get("farmer_id") != farmer_id:
        raise NotFoundError("Booking not found")
    if booking.get("status") != "booked":
        raise ConflictError("This booking is not active")

    slot_date = booking["slot_date"]
    slot_date_value = slot_date if hasattr(slot_date, "isoformat") else date_type.fromisoformat(str(slot_date))
    # Same procurement-centre business timezone slot_service.py's original
    # booking-date check uses (not the server process's local timezone),
    # so "today" means the same thing on both sides of the check-in flow.
    if slot_date_value > datetime.now(PROCUREMENT_CENTRE_TIMEZONE).date():
        raise ConflictError("You can only check in on or after your slot date")

    joined_at = utcnow()
    queue_date = _queue_date_at(joined_at)
    queue_id = str(uuid.uuid4())
    record = queue_repo.create_check_in(
        queue_id,
        booking["centre_id"],
        {
            "booking_id": booking["booking_id"],
            "farmer_id": farmer_id,
            "centre_id": booking["centre_id"],
            "status": "waiting",
            "joined_at": joined_at,
            "queue_date": queue_date,
            "resolved_at": None,
        },
    )
    if record is None:
        raise ConflictError("You already have an active queue entry, or this booking already checked in")

    _dispatch_check_in_notification(farmer_repo, record)
    return _to_out(queue_repo, record)


def get_my_queue_status(queue_repo: QueueRepository, farmer_id: str) -> QueueEntryOut:
    """Get the authenticated farmer's current active (waiting) queue entry."""
    record = queue_repo.get_active_for_farmer(farmer_id)
    if record is None:
        raise NotFoundError("No active queue entry")
    return _to_out(queue_repo, record)


def get_queue_entry(queue_repo: QueueRepository, farmer_id: str, queue_id: str) -> QueueEntryOut:
    """Get a specific queue entry owned by the authenticated farmer."""
    record = queue_repo.get(queue_id)
    if record is None or record.get("farmer_id") != farmer_id:
        raise NotFoundError("Queue entry not found")
    return _to_out(queue_repo, record)


def _resolve(queue_repo: QueueRepository, farmer_id: str, queue_id: str, new_status: str) -> QueueEntryOut:
    """Mark a queue entry as resolved with the given terminal status (served or left)."""
    record = queue_repo.resolve(queue_id, farmer_id, new_status, utcnow())
    if record is None:
        raise NotFoundError("Active queue entry not found")
    return _to_out(queue_repo, record)


def complete_queue_entry(queue_repo: QueueRepository, farmer_id: str, queue_id: str) -> QueueEntryOut:
    """Mark the farmer's own queue entry as served (self-reported, procurement complete)."""
    return _resolve(queue_repo, farmer_id, queue_id, "served")


def leave_queue(queue_repo: QueueRepository, farmer_id: str, queue_id: str) -> QueueEntryOut:
    """Cancel the farmer's own queue entry without being served."""
    return _resolve(queue_repo, farmer_id, queue_id, "left")


def get_centre_queue_status(
    queue_repo: QueueRepository, centre_repo: CentreRepository, centre_id: str
) -> QueueCentreStatusOut:
    """Get aggregate, identity-free live queue status for a centre."""
    if centre_repo.get(centre_id) is None:
        raise NotFoundError("Procurement centre not found")
    queue_date = _queue_date_at(utcnow())
    waiting = queue_repo.count_waiting(centre_id, queue_date)
    return QueueCentreStatusOut(
        centre_id=centre_id,
        waiting_count=waiting,
        estimated_wait_minutes=waiting * AVERAGE_SERVICE_MINUTES,
    )
