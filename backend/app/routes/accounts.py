from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify, request

from app import get_session
from app.models import Account

bp = APIBlueprint("accounts", __name__, tag="Accounts")

MAX_NAME_LENGTH = 100
MAX_AMOUNT_VALUE = 1_000_000_000  # 1 billion


@bp.get("/api/accounts")
def list_accounts() -> Response:
    """List all accounts."""
    session = get_session()
    accounts = session.query(Account).order_by(Account.name).all()
    return jsonify([a.to_dict() for a in accounts])


@bp.post("/api/accounts")
def create_account() -> Response | tuple[Response, int]:
    """Create a new account.

    Requires name. Optional: balance (default 0), is_credit (default false).
    """
    session = get_session()
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    if "name" not in data:
        return jsonify({"error": "name is required"}), 400

    name = str(data["name"]).strip()
    if not name or len(name) > MAX_NAME_LENGTH:
        return jsonify({"error": f"name must be 1-{MAX_NAME_LENGTH} characters"}), 400

    balance = Decimal(str(data.get("balance", 0)))
    if abs(balance) > MAX_AMOUNT_VALUE:
        return jsonify({"error": "balance exceeds maximum allowed value"}), 400

    account = Account(
        name=name,
        balance=balance,
        is_credit=bool(data.get("is_credit", False)),
    )
    session.add(account)
    session.commit()

    return jsonify(account.to_dict()), 201


@bp.put("/api/accounts/<int:account_id>")
def update_account(account_id: int) -> Response | tuple[Response, int]:
    """Update an existing account."""
    session = get_session()
    account = session.query(Account).filter_by(id=account_id).first()

    if not account:
        return jsonify({"error": "Account not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    if "name" in data:
        name = str(data["name"]).strip()
        if not name or len(name) > MAX_NAME_LENGTH:
            return (
                jsonify({"error": f"name must be 1-{MAX_NAME_LENGTH} characters"}),
                400,
            )
        account.name = name
    if "balance" in data:
        balance = Decimal(str(data["balance"]))
        if abs(balance) > MAX_AMOUNT_VALUE:
            return jsonify({"error": "balance exceeds maximum allowed value"}), 400
        account.balance = balance
    if "is_credit" in data:
        account.is_credit = bool(data["is_credit"])

    session.commit()
    return jsonify(account.to_dict())


@bp.delete("/api/accounts/<int:account_id>")
def delete_account(account_id: int) -> tuple[Response, int]:
    """Delete an account."""
    session = get_session()
    account = session.query(Account).filter_by(id=account_id).first()

    if not account:
        return jsonify({"error": "Account not found"}), 404

    session.delete(account)
    session.commit()
    return jsonify({"message": "Account deleted"}), 200
