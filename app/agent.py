"""The reception agent core.

Classifies the customer intent, qualifies the request against the business
profile, generates booking slots, and produces a reply. Uses the OpenAI API
when a key is available, and falls back to deterministic logic otherwise.
"""

from __future__ import annotations

import json
import os

from pydantic import BaseModel

from app.config import BusinessProfile
from app.scheduler import suggest_slots

_BOOKING_WORDS = (
    "book",
    "booking",
    "appointment",
    "slot",
    "reserve",
    "schedule",
    "available",
    "availability",
    "when can",
)
_FAQ_WORDS = (
    "open",
    "hours",
    "price",
    "cost",
    "how much",
    "parking",
    "pay",
    "payment",
    "where",
    "address",
    "walk in",
)


class AgentResponse(BaseModel):
    """Structured output returned by the agent for every message."""

    reply: str
    intent: str
    qualified: bool
    suggested_slots: list[str]


def _classify_intent(message: str) -> str:
    """Heuristically classify the customer intent.

    Args:
        message: The raw customer message.

    Returns:
        One of ``booking``, ``faq``, or ``other``.
    """
    text = message.lower()
    if any(word in text for word in _BOOKING_WORDS):
        return "booking"
    if any(word in text for word in _FAQ_WORDS) or "?" in text:
        return "faq"
    return "other"


def _match_service(message: str, profile: BusinessProfile) -> str | None:
    """Return the name of the first service mentioned in the message, if any."""
    text = message.lower()
    for service in profile.services:
        first_word = service.name.lower().split()[0]
        if service.name.lower() in text or first_word in text:
            return service.name
    return None


def _profile_summary(profile: BusinessProfile) -> str:
    """Build a compact text summary of the business profile for grounding."""
    services = "; ".join(
        f"{s.name} ({s.duration_minutes} min, {s.price})" for s in profile.services
    )
    hours = "; ".join(
        f"{day} {h.open}-{h.close}" for day, h in profile.opening_hours.items()
    )
    faqs = "; ".join(f"Q: {f.q} A: {f.a}" for f in profile.faqs)
    return (
        f"Business: {profile.name}. Address: {profile.address}. "
        f"Phone: {profile.phone}. Services: {services}. "
        f"Opening hours: {hours}. FAQs: {faqs}."
    )


def _fallback_reply(
    message: str,
    profile: BusinessProfile,
    intent: str,
    slots: list[str],
) -> str:
    """Produce a deterministic reply when no LLM key is configured."""
    service = _match_service(message, profile)

    if intent == "faq":
        text = message.lower()
        for faq in profile.faqs:
            if any(token in text for token in faq.q.lower().split() if len(token) > 3):
                return faq.a
        return (
            f"{profile.name} is here to help. You can reach us at {profile.phone} "
            f"or visit {profile.address}."
        )

    if intent == "booking":
        opener = (
            f"Yes, we offer {service.lower()}."
            if service
            else "I can help you book an appointment."
        )
        if slots:
            return f"{opener} Here are some times I can hold for you."
        return (
            f"{opener} I do not see free slots in the next few days, "
            f"please call us at {profile.phone}."
        )

    return (
        f"Thanks for messaging {profile.name}. "
        "Let me know if you would like to book an appointment or ask about our services."
    )


def _llm_reply(
    message: str,
    profile: BusinessProfile,
    intent: str,
    slots: list[str],
    api_key: str,
) -> str:
    """Generate a grounded reply using the OpenAI Chat Completions API.

    Args:
        message: The customer message.
        profile: The business profile used for grounding.
        intent: The classified intent.
        slots: Pre computed booking slots to offer.
        api_key: The OpenAI API key.

    Returns:
        The model generated reply text.
    """
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    system = (
        "You are the receptionist for a small business. Answer only using the "
        "business information provided. Be warm, concise, and never invent "
        "services, prices, or hours. If the customer wants to book and slots are "
        "provided, offer them naturally without listing raw timestamps.\n\n"
        f"{_profile_summary(profile)}"
    )
    user = (
        f"Customer message: {message}\n"
        f"Detected intent: {intent}\n"
        f"Available slots (ISO): {json.dumps(slots)}\n"
        "Write a single short reply to the customer."
    )

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.4,
        max_tokens=180,
    )
    return (completion.choices[0].message.content or "").strip()


def handle_message(message: str, profile: BusinessProfile) -> AgentResponse:
    """Process one customer message into a structured agent response.

    Args:
        message: The incoming customer message.
        profile: The validated business profile.

    Returns:
        An :class:`AgentResponse` with reply, intent, qualified flag, and slots.
    """
    intent = _classify_intent(message)
    slots = suggest_slots(profile) if intent == "booking" else []
    service = _match_service(message, profile)
    qualified = intent == "booking" and (service is not None or bool(slots))

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key:
        try:
            reply = _llm_reply(message, profile, intent, slots, api_key)
        except Exception:
            reply = _fallback_reply(message, profile, intent, slots)
    else:
        reply = _fallback_reply(message, profile, intent, slots)

    return AgentResponse(
        reply=reply,
        intent=intent,
        qualified=qualified,
        suggested_slots=slots,
    )
