"""Generic SMS gateway client.

Covers the "SMS gateway/API" line in team_work_division.md's Backend
Developer responsibilities ("Integrate SMS gateway for OTP/notifications").
No specific SMS vendor has been chosen yet (technology_stack.md just lists
"SMS gateway/API" generically), so this sends a generic JSON POST
(`{"to": ..., "message": ...}`, Bearer-authenticated) to
SMS_GATEWAY_BASE_URL - update the payload shape here once a vendor is
picked; nothing else in the codebase needs to change (same
integration-point pattern as app/services/congestion_service.py uses for
AI/ML's endpoint).

Degrades gracefully (logs and returns False) when SMS_GATEWAY_BASE_URL
isn't configured - the same graceful-fallback shape used throughout this
backend (app/core/firebase.py, app/services/congestion_service.py) so
local dev/tests never need a real SMS gateway.
"""
import logging

import httpx

from app.core.config import Settings

logger = logging.getLogger("app.sms")


def send_sms(settings: Settings, phone_number: str, message: str) -> bool:
    """Send an SMS, or log a generic event when no gateway is configured.

    Best-effort: never raises. Callers should treat this as a side effect,
    not a required step - see app/services/queue_service.py,
    app/services/otp_service.py, and app/services/slot_service.py for how
    failures are handled (logged and swallowed, never block the primary
    operation).
    """
    if settings.twilio_account_sid and settings.twilio_auth_token:
        # Use Twilio API
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
            response = httpx.post(
                url,
                data={
                    "To": phone_number,
                    "From": settings.twilio_from_number,
                    "Body": message
                },
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
                timeout=settings.sms_gateway_timeout_seconds,
            )
            response.raise_for_status()
            return True
        except Exception:
            logger.exception("Failed to send SMS via Twilio")
            return False

    if not settings.sms_gateway_base_url:
        logger.info(f"SMS delivery skipped: gateway not configured. Message: {message}")
        return False

    try:
        headers = {}
        if settings.sms_gateway_api_key:
            headers["Authorization"] = f"Bearer {settings.sms_gateway_api_key}"
        response = httpx.post(
            settings.sms_gateway_base_url,
            json={"to": phone_number, "message": message},
            headers=headers,
            timeout=settings.sms_gateway_timeout_seconds,
        )
        response.raise_for_status()
        return True
    except Exception:  # pragma: no cover - depends on live SMS gateway
        logger.exception("Failed to send SMS via generic gateway")
        return False
