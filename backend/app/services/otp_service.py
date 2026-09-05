"""Phone-number OTP verification business logic (see app/schemas/otp.py).

The OTP challenge (hash, expiry, attempt count) is stored as extra fields
on the farmer's own repository record via FarmerRepository.update - the
same repository Phase 1 already provides - rather than a new collection,
since there is at most one pending challenge per farmer at a time. These
fields are never part of FarmerOut (see app/schemas/farmer.py), so they
never leak in API responses, the same way aadhaar_hash already doesn't.
"""
import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.sms import send_sms
from app.repositories.base import FarmerRepository, OtpVerificationResult
from app.schemas.otp import OtpRequestOut, OtpVerifyOut
from app.services.queue_service import dispatch_notification

logger = logging.getLogger("app.otp")


def _hash_code(code: str, secret: str) -> str:
    """Derive an OTP digest using the server-held HMAC secret."""
    return hmac.new(
        secret.encode("utf-8"),
        code.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def utcnow() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def _format_expiration(ttl_seconds: int) -> str:
    """Format an OTP lifetime as human-readable string without rounding sub-minute values to zero."""
    if ttl_seconds < 60:
        unit = "second" if ttl_seconds == 1 else "seconds"
        return f"{ttl_seconds} {unit}"

    minutes = (ttl_seconds + 59) // 60
    unit = "minute" if minutes == 1 else "minutes"
    return f"{minutes} {unit}"


def _deliver_otp(settings: Settings, phone_number: str, message: str) -> None:
    """Send an OTP from a worker and retain unsuccessful-delivery logging."""
    if not send_sms(settings, phone_number, message):
        logger.info("OTP delivery was not completed")


def request_otp(settings: Settings, farmer_repo: FarmerRepository, farmer_id: str) -> OtpRequestOut:
    """Generate and send a phone-verification OTP to the farmer's registered number."""
    farmer = farmer_repo.get(farmer_id)
    if farmer is None:
        raise NotFoundError("Farmer profile not found - register first")
    phone_number = farmer.get("phone_number")
    if not phone_number:
        raise ConflictError("No phone number on file for this profile")

    issued_at = utcnow()
    code = f"{secrets.randbelow(10 ** settings.otp_length):0{settings.otp_length}d}"
    expires_at = issued_at + timedelta(seconds=settings.otp_ttl_seconds)
    issued = farmer_repo.issue_phone_otp_challenge(
        farmer_id,
        issued_at,
        settings.otp_request_cooldown_seconds,
        {
            "phone_otp_hash": _hash_code(code, settings.otp_hmac_secret),
            "phone_otp_expires_at": expires_at,
            "phone_otp_attempts": 0,
        },
    )
    if not issued:
        raise ConflictError("Please wait before requesting another verification code")

    message = (
        f"Krishka Vachana: your verification code is {code}. "
        f"It expires in {_format_expiration(settings.otp_ttl_seconds)}."
    )
    dispatch_notification(
        lambda: _deliver_otp(settings, phone_number, message),
        "OTP delivery",
    )

    return OtpRequestOut(message="Verification code sent", expires_in_seconds=settings.otp_ttl_seconds)


def verify_otp(settings: Settings, farmer_repo: FarmerRepository, farmer_id: str, otp_code: str) -> OtpVerifyOut:
    """Verify a submitted OTP code against the farmer's pending challenge."""
    result = farmer_repo.consume_phone_otp_attempt(
        farmer_id,
        _hash_code(otp_code, settings.otp_hmac_secret),
        utcnow(),
        settings.otp_max_attempts,
    )
    if result is OtpVerificationResult.NOT_FOUND:
        raise NotFoundError("Farmer profile not found - register first")
    if result is OtpVerificationResult.MISSING:
        raise ConflictError("No verification code was requested, or it already expired")
    if result is OtpVerificationResult.EXPIRED:
        raise ConflictError("Verification code expired - request a new one")
    if result is OtpVerificationResult.LOCKED:
        raise ConflictError("Too many incorrect attempts - request a new code")
    if result is OtpVerificationResult.INCORRECT:
        raise ValidationAppError("Incorrect verification code")
    return OtpVerifyOut(phone_verified=True)
