"""Shared request validation for the API routes.

The helpers raise ``InvalidInput``. Each blueprint registers
``invalid_input_response`` for it, so a failed check becomes the API's usual
``{"error": message}`` with a 400 instead of escaping as a 500.
"""

import math
from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify

MAX_NAME_LENGTH = 100
MAX_AMOUNT_VALUE = 1_000_000_000  # 1 billion

# A recurrence of up to 1200 units: 100 years of months, and far less for days
# and weeks. It keeps frequency_value inside the integer column and keeps the
# date arithmetic in deadline_calc inside the range date and timedelta allow.
MAX_FREQUENCY_VALUE = 1200

# Bounds of a PostgreSQL integer column.
INT32_MIN = -(2**31)
INT32_MAX = 2**31 - 1


class InvalidInput(Exception):
    """A request value failed validation; the API answers 400."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def invalid_input_response(err: InvalidInput) -> tuple[Response, int]:
    """Error handler that turns InvalidInput into the API's 400 shape."""
    return jsonify({"error": err.message}), 400


def register_validation(bp: APIBlueprint) -> None:
    """Answer InvalidInput raised by this blueprint's views with a 400."""
    bp.register_error_handler(InvalidInput, invalid_input_response)


def is_finite_number(value: object) -> bool:
    """True for a JSON number that is neither NaN nor infinite (not a bool)."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value)


def parse_decimal(value: object, field: str) -> Decimal:
    """Parse a number or numeric string into a finite Decimal.

    NaN, sNaN and Infinity parse as Decimals but break comparisons and cannot
    be stored or serialised, so they are rejected here with the rest.
    """
    if isinstance(value, bool):
        raise InvalidInput(f"{field} must be a number")
    try:
        number = Decimal(str(value))
    except (ArithmeticError, ValueError, TypeError):
        raise InvalidInput(f"{field} must be a number") from None
    if not number.is_finite():
        raise InvalidInput(f"{field} must be a finite number")
    return number


def parse_amount(value: object, field: str) -> Decimal:
    """Parse a signed money value within the API's maximum magnitude."""
    amount = parse_decimal(value, field)
    if abs(amount) > MAX_AMOUNT_VALUE:
        raise InvalidInput(f"{field} exceeds maximum allowed value")
    return amount


def parse_percentage(value: object, field: str) -> Decimal:
    """Parse a percentage between 0 and 100."""
    pct = parse_decimal(value, field)
    if pct < 0 or pct > 100:
        raise InvalidInput(f"{field} must be between 0 and 100")
    return pct


def parse_int(
    value: object,
    field: str,
    minimum: int = INT32_MIN,
    maximum: int = INT32_MAX,
    range_error: str | None = None,
) -> int:
    """Parse an integer the way the routes always have, within bounds."""
    try:
        number: int = int(value)  # type: ignore[call-overload]
    except (ValueError, TypeError, OverflowError):
        raise InvalidInput(f"{field} must be an integer") from None
    if number < minimum or number > maximum:
        raise InvalidInput(
            range_error or f"{field} must be between {minimum} and {maximum}"
        )
    return number


def parse_frequency_value(value: object) -> int:
    """Parse a recurrence multiplier between 1 and MAX_FREQUENCY_VALUE."""
    return parse_int(value, "frequency_value", 1, MAX_FREQUENCY_VALUE)


def parse_name(value: object, field: str = "name") -> str:
    """Strip a display name and check its length as the create routes do."""
    if value is None:
        raise InvalidInput(f"{field} is required")
    name = str(value).strip()
    if not name or len(name) > MAX_NAME_LENGTH:
        raise InvalidInput(f"{field} must be 1-{MAX_NAME_LENGTH} characters")
    return name
