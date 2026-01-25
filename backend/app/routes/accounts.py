from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify, request

from app import get_session
from app.models import Account

bp = APIBlueprint("accounts", __name__, tag="Accounts")


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

    account = Account(
        name=data["name"],
        balance=Decimal(str(data.get("balance", 0))),
        is_credit=data.get("is_credit", False),
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
        account.name = data["name"]
    if "balance" in data:
        account.balance = Decimal(str(data["balance"]))
    if "is_credit" in data:
        account.is_credit = data["is_credit"]

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
