"""Business profile loading and validation.

This module reads the business profile from a YAML file into typed Pydantic
models so the rest of the app can rely on a validated, structured config.
"""

from __future__ import annotations

import os

import yaml
from pydantic import BaseModel, Field


class Service(BaseModel):
    """A single bookable service offered by the business."""

    name: str
    duration_minutes: int = 30
    price: str = ""


class DayHours(BaseModel):
    """Opening and closing time for one weekday in 24h HH:MM format."""

    open: str
    close: str


class BookingRules(BaseModel):
    """Rules that constrain how booking slots are generated."""

    slot_minutes: int = 30
    lead_time_hours: int = 2
    horizon_days: int = 7
    max_suggestions: int = 3


class Faq(BaseModel):
    """A single frequently asked question and its canned answer."""

    q: str
    a: str


class BusinessProfile(BaseModel):
    """Full business profile used to ground every agent reply."""

    name: str
    timezone: str = "UTC"
    phone: str = ""
    address: str = ""
    services: list[Service] = Field(default_factory=list)
    opening_hours: dict[str, DayHours] = Field(default_factory=dict)
    booking_rules: BookingRules = Field(default_factory=BookingRules)
    faqs: list[Faq] = Field(default_factory=list)


def load_business_profile(path: str | None = None) -> BusinessProfile:
    """Load and validate the business profile from a YAML file.

    Args:
        path: Optional path to the YAML config. Falls back to the
            ``BUSINESS_CONFIG`` env var, then ``config/business.yaml``.

    Returns:
        A validated :class:`BusinessProfile`.

    Raises:
        FileNotFoundError: If the resolved config file does not exist.
    """
    resolved = path or os.getenv("BUSINESS_CONFIG", "config/business.yaml")
    with open(resolved, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return BusinessProfile.model_validate(raw)
