from decimal import Decimal

from flask import Blueprint, jsonify, request

from app import get_session
from app.models import Account

bp = Blueprint("accounts", __name__)


@bp.route("/api/accounts", methods=["GET"])
def list_accounts():
    """List all accounts."""
    session = get_session()
    accounts = session.query(Account).order_by(Account.name).all()
    return jsonify([a.to_dict() for a in accounts])


@bp.route("/api/accounts", methods=["POST"])
def create_account():
    """Create a new account."""
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


@bp.route("/api/accounts/<int:account_id>", methods=["PUT"])
def update_account(account_id: int):
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


@bp.route("/api/accounts/<int:account_id>", methods=["DELETE"])
def delete_account(account_id: int):
    """Delete an account."""
    session = get_session()
    account = session.query(Account).filter_by(id=account_id).first()

    if not account:
        return jsonify({"error": "Account not found"}), 404

    session.delete(account)
    session.commit()
    return jsonify({"message": "Account deleted"}), 200
