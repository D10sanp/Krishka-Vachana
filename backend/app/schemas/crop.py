"""Crop & quantity registration schemas.

Covers the "Crop and quantity registration" feature - the second stage of
the sample flow (Farmer -> Smart Slot -> ...). Procurement-centre selection
and slot booking are a separate, later phase (see roadmap in the PR
description) and are intentionally not in this module yet.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.time import utcnow

# Common procurement crops. Kept open-ended via "other" so this isn't a hard
# blocker if a state's mandi handles something not listed here yet.
COMMON_CROPS = {
    "wheat",
    "paddy",
    "cotton",
    "sugarcane",
    "maize",
    "soybean",
    "groundnut",
    "mustard",
    "gram",
    "other",
}


class CropRegistrationCreate(BaseModel):
    """Schema for registering a new crop and quantity."""

    crop_type: str = Field(description=f"One of {sorted(COMMON_CROPS)}")
    crop_type_other: Optional[str] = Field(
        default=None, description="Required when crop_type == 'other'", max_length=80
    )
    quantity_quintals: float = Field(gt=0, le=100000)
    notes: Optional[str] = Field(default=None, max_length=280)

    @field_validator("crop_type")
    @classmethod
    def validate_crop_type(cls, v: str) -> str:
        """Validate and normalize crop type to lowercase."""
        v = v.lower().strip()
        if v not in COMMON_CROPS:
            raise ValueError(f"crop_type must be one of {sorted(COMMON_CROPS)}")
        return v

    @field_validator("crop_type_other")
    @classmethod
    def normalize_crop_type_other(cls, v: Optional[str]) -> Optional[str]:
        """Strip whitespace from crop_type_other if provided."""
        return v.strip() if v is not None else None

    @model_validator(mode="after")
    def validate_other(self) -> "CropRegistrationCreate":
        """Validate that crop_type_other is provided when crop_type is 'other'."""
        if self.crop_type == "other" and not self.crop_type_other:
            raise ValueError("crop_type_other is required when crop_type is 'other'")
        return self


class CropOut(BaseModel):
    """Schema for crop registration responses."""

    crop_id: str
    farmer_id: str
    crop_type: str
    crop_type_other: Optional[str] = None
    quantity_quintals: float
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
