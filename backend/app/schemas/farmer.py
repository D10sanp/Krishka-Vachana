"""Farmer identity & profile schemas.

Covers the "Farmer ID / Aadhaar-linked identification" feature from the
project brief. `farmer_id` is the Firebase Auth UID (identity itself is
Infra's domain); this module only handles the *profile* data attached to
that identity, which is Backend's responsibility.

Security note: we never accept or return a full Aadhaar number in any
response. Only the last 4 digits are stored/exposed (`aadhaar_last4`),
mirroring how Aadhaar is handled in real e-KYC flows. The full number is
validated on input, converted to a keyed fingerprint, and discarded - see
app/services/farmer_service.py.
"""
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.core.time import utcnow

# Keep this list in sync with what the AI/ML and Frontend teams support for
# the "regional language capability" requirement. Extend as needed.
SUPPORTED_LANGUAGES = {"en", "hi", "mr", "pa", "gu", "ta", "te", "kn", "bn", "or", "ml"}

_AADHAAR_RE = re.compile(r"^\d{12}$")
_PHONE_RE = re.compile(r"^[6-9]\d{9}$")  # Indian mobile numbers


class FarmerCreate(BaseModel):
    """Schema for creating a new farmer profile with Aadhaar-linked identification."""

    full_name: str = Field(min_length=2, max_length=120)
    phone_number: str = Field(description="10-digit Indian mobile number, no country code")
    aadhaar_number: str = Field(description="12-digit Aadhaar number; never stored or returned in full")
    village: str = Field(min_length=1, max_length=120)
    district: str = Field(min_length=1, max_length=120)
    state: str = Field(min_length=1, max_length=120)
    preferred_language: str = Field(default="en")

    @field_validator("full_name", "village", "district", "state")
    @classmethod
    def strip_and_require_length(cls, v: str, info) -> str:
        """Strip whitespace and validate minimum length requirements."""
        v = v.strip()
        minimum = 2 if info.field_name == "full_name" else 1
        if len(v) < minimum:
            raise ValueError(
                f"{info.field_name} must be at least {minimum} character(s) "
                "after trimming whitespace"
            )
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate that phone number is a 10-digit Indian mobile number."""
        if not _PHONE_RE.match(v):
            raise ValueError("phone_number must be a 10-digit Indian mobile number")
        return v

    @field_validator("aadhaar_number")
    @classmethod
    def validate_aadhaar(cls, v: str) -> str:
        """Validate that Aadhaar number is exactly 12 digits."""
        if not _AADHAAR_RE.match(v):
            raise ValueError("aadhaar_number must be exactly 12 digits")
        return v

    @field_validator("preferred_language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        """Validate that preferred language is in the supported languages list."""
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(f"preferred_language must be one of {sorted(SUPPORTED_LANGUAGES)}")
        return v


class FarmerUpdate(BaseModel):
    """Schema for updating a farmer profile (all fields optional)."""

    full_name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    village: Optional[str] = Field(default=None, min_length=1, max_length=120)
    district: Optional[str] = Field(default=None, min_length=1, max_length=120)
    state: Optional[str] = Field(default=None, min_length=1, max_length=120)
    preferred_language: Optional[str] = None

    @field_validator("full_name", "village", "district", "state")
    @classmethod
    def strip_and_require_length(cls, v: Optional[str], info) -> Optional[str]:
        """Strip whitespace and validate minimum length requirements for optional fields."""
        if v is None:
            return v
        v = v.strip()
        minimum = 2 if info.field_name == "full_name" else 1
        if len(v) < minimum:
            raise ValueError(
                f"{info.field_name} must be at least {minimum} character(s) "
                "after trimming whitespace"
            )
        return v

    @field_validator("preferred_language")
    @classmethod
    def validate_language(cls, v: Optional[str]) -> Optional[str]:
        """Validate that preferred language is in the supported languages list (if provided)."""
        if v is not None and v not in SUPPORTED_LANGUAGES:
            raise ValueError(f"preferred_language must be one of {sorted(SUPPORTED_LANGUAGES)}")
        return v


class FarmerOut(BaseModel):
    """Schema for farmer profile responses (excludes full Aadhaar number)."""

    farmer_id: str
    full_name: str
    phone_number: str
    aadhaar_last4: str
    village: str
    district: str
    state: str
    preferred_language: str
    phone_verified: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}
