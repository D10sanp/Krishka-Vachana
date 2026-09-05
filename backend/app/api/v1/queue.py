from html import escape

from fastapi import APIRouter, Depends, status
from fastapi.responses import HTMLResponse

from app.api.deps import (
    get_centre_repository,
    get_current_farmer_uid,
    get_farmer_repository,
    get_queue_repository,
    get_slot_booking_repository,
)
from app.core.branding import page_shell
from app.repositories.base import CentreRepository, FarmerRepository, QueueRepository, SlotBookingRepository
from app.schemas.queue import QueueCentreStatusOut, QueueCheckInCreate, QueueEntryOut
from app.services import queue_service

router = APIRouter(prefix="/queue", tags=["queue"])


@router.post("/check-in", response_model=QueueEntryOut, status_code=status.HTTP_201_CREATED)
def check_in(
    payload: QueueCheckInCreate,
    farmer_id: str = Depends(get_current_farmer_uid),
    queue_repo: QueueRepository = Depends(get_queue_repository),
    booking_repo: SlotBookingRepository = Depends(get_slot_booking_repository),
    farmer_repo: FarmerRepository = Depends(get_farmer_repository),
) -> QueueEntryOut:
    """Check the authenticated farmer in to their booked centre's live queue."""
    return queue_service.check_in(queue_repo, booking_repo, farmer_repo, farmer_id, payload)


@router.get("/me", response_model=QueueEntryOut)
def get_my_status(
    farmer_id: str = Depends(get_current_farmer_uid),
    queue_repo: QueueRepository = Depends(get_queue_repository),
) -> QueueEntryOut:
    """Get the authenticated farmer's active queue entry and live position."""
    return queue_service.get_my_queue_status(queue_repo, farmer_id)


@router.get("/centre/{centre_id}", response_model=QueueCentreStatusOut)
def get_centre_status(
    centre_id: str,
    _farmer_id: str = Depends(get_current_farmer_uid),
    queue_repo: QueueRepository = Depends(get_queue_repository),
    centre_repo: CentreRepository = Depends(get_centre_repository),
) -> QueueCentreStatusOut:
    """Get aggregate, identity-free live queue status for a centre."""
    return queue_service.get_centre_queue_status(queue_repo, centre_repo, centre_id)


@router.get("/{queue_id}", response_model=QueueEntryOut)
def get_entry(
    queue_id: str,
    farmer_id: str = Depends(get_current_farmer_uid),
    queue_repo: QueueRepository = Depends(get_queue_repository),
) -> QueueEntryOut:
    """Get a specific queue entry owned by the authenticated farmer."""
    return queue_service.get_queue_entry(queue_repo, farmer_id, queue_id)


@router.post("/{queue_id}/complete", response_model=QueueEntryOut)
def complete_entry(
    queue_id: str,
    farmer_id: str = Depends(get_current_farmer_uid),
    queue_repo: QueueRepository = Depends(get_queue_repository),
) -> QueueEntryOut:
    """Mark the farmer's own queue entry as served (self-reported, procurement complete)."""
    return queue_service.complete_queue_entry(queue_repo, farmer_id, queue_id)


@router.post("/{queue_id}/leave", response_model=QueueEntryOut)
def leave_entry(
    queue_id: str,
    farmer_id: str = Depends(get_current_farmer_uid),
    queue_repo: QueueRepository = Depends(get_queue_repository),
) -> QueueEntryOut:
    """Cancel the farmer's own queue entry without being served."""
    return queue_service.leave_queue(queue_repo, farmer_id, queue_id)


@router.get("/{queue_id}/token", response_class=HTMLResponse, include_in_schema=False)
def printable_token(
    queue_id: str,
    farmer_id: str = Depends(get_current_farmer_uid),
    queue_repo: QueueRepository = Depends(get_queue_repository),
    centre_repo: CentreRepository = Depends(get_centre_repository),
    farmer_repo: FarmerRepository = Depends(get_farmer_repository),
) -> HTMLResponse:
    """Branded, printer-friendly token page.

    For farmers without a smart device (or whoever is helping them) to
    print or show at the centre. Same spirit and disclaimer as /docs and
    /status in app/api/docs.py / app/core/branding.py: not part of the
    real frontend product surface, just enough branding for a fallback
    page reachable directly in a browser. Ownership-checked like every
    other /queue endpoint - a farmer can only print their own token.
    """
    entry = queue_service.get_queue_entry(queue_repo, farmer_id, queue_id)
    centre = centre_repo.get(entry.centre_id)
    farmer = farmer_repo.get(farmer_id)
    centre_name = escape(str(centre["name"] if centre else entry.centre_id))
    farmer_name = escape(str(farmer.get("full_name") or "")) if farmer else ""

    if entry.status == "waiting" and entry.position is not None:
        status_line = f"Position {entry.position} in the queue"
    elif entry.status == "served":
        status_line = "This token has already been served."
    elif entry.status == "left":
        status_line = "This token was cancelled."
    else:  # pragma: no cover - QUEUE_STATUSES is exhaustive today
        status_line = entry.status

    body = f"""
      <div class="card" style="text-align:center;">
        <span class="badge badge-ok">Krishka Vachana Token</span>
        <div style="font-size:56px;font-weight:700;color:#123524;margin:16px 0;">#{entry.token_number}</div>
        <p style="font-size:18px;margin:4px 0;">{farmer_name}</p>
        <p style="color:#68756D;margin:2px 0;">{centre_name}</p>
        <p style="color:#68756D;margin:2px 0;">{entry.joined_at.strftime('%d %b %Y')}</p>
        <p style="margin-top:16px;font-weight:600;">{status_line}</p>
      </div>
      <p style="text-align:center;color:#68756D;font-size:13px;">
        Print this page (Ctrl/Cmd+P) to carry a paper copy of your token.
      </p>
    """
    return HTMLResponse(page_shell(f"Token #{entry.token_number}", body))
