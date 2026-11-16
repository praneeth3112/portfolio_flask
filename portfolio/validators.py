"""Server-side validation for the contact form."""
from __future__ import annotations

import re
from typing import Any

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

NAME_MIN, NAME_MAX = 2, 80
EMAIL_MAX = 254
MESSAGE_MIN, MESSAGE_MAX = 10, 2000


class ValidationError(Exception):
    """Raised when a payload fails validation; ``errors`` maps field -> message."""

    def __init__(self, errors: dict[str, str]):
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))
        self.errors = errors


def clean_text(value: Any) -> str:
    """Coerce to str, drop control characters and trim whitespace."""
    if value is None:
        return ""
    return CONTROL_CHARS_RE.sub("", str(value)).strip()


def validate_contact(payload: Any) -> dict[str, str]:
    """Validate and normalise a contact-form payload.

    Returns the cleaned ``{"name", "email", "message"}`` dict or raises
    :class:`ValidationError`. A filled ``website`` field is a honeypot: real
    users never see it, so bots that fill it are rejected.
    """
    if not isinstance(payload, dict):
        raise ValidationError({"form": "Expected a JSON object."})

    if clean_text(payload.get("website")):
        raise ValidationError({"form": "Submission rejected."})

    name = clean_text(payload.get("name"))
    email = clean_text(payload.get("email")).lower()
    message = clean_text(payload.get("message"))
    errors: dict[str, str] = {}

    if not NAME_MIN <= len(name) <= NAME_MAX:
        errors["name"] = f"Name must be {NAME_MIN}-{NAME_MAX} characters."
    if len(email) > EMAIL_MAX or not EMAIL_RE.match(email):
        errors["email"] = "Enter a valid email address."
    if not MESSAGE_MIN <= len(message) <= MESSAGE_MAX:
        errors["message"] = f"Message must be {MESSAGE_MIN}-{MESSAGE_MAX} characters."

    if errors:
        raise ValidationError(errors)
    return {"name": name, "email": email, "message": message}
