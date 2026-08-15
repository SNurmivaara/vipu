"""Tests for budget API endpoints."""

import pytest


class TestValidation:
    """Tests for input validation across all budget endpoints."""

    def test_account_missing_name(self, client):
        """POST /api/accounts requires name."""
        response = client.post("/api/accounts", json={"balance": 1000})
        assert response.status_code == 400
        assert "name" in response.json["error"].lower()

    def test_account_empty_name(self, client):
        """POST /api/accounts rejects empty name."""
        response = client.post("/api/accounts", json={"name": "", "balance": 1000})
        assert response.status_code == 400

    def test_account_name_too_long(self, client):
        """POST /api/accounts rejects name > 100 chars."""
        response = client.post("/api/accounts", json={"name": "x" * 101, "balance": 0})
        assert response.status_code == 400

    def test_account_balance_exceeds_max(self, client):
        """POST /api/accounts rejects balance > 1 billion."""
        response = client.post(
            "/api/accounts", json={"name": "Big", "balance": 1_000_000_001}
        )
        assert response.status_code == 400

    def test_account_no_body(self, client):
        """POST /api/accounts with no body returns 400."""
        response = client.post("/api/accounts", content_type="application/json")
        assert response.status_code == 400

    def test_income_missing_name(self, client):
        """POST /api/income requires name."""
        response = client.post("/api/income", json={"gross_amount": 1000})
        assert response.status_code == 400

    def test_income_amount_exceeds_max(self, client):
        """POST /api/income rejects amount > 1 billion."""
        response = client.post(
            "/api/income", json={"name": "Big", "gross_amount": 1_000_000_001}
        )
        assert response.status_code == 400

    def test_expense_missing_name(self, client):
        """POST /api/expenses requires name."""
        response = client.post("/api/expenses", json={"amount": 100})
        assert response.status_code == 400

    def test_expense_amount_exceeds_max(self, client):
        """POST /api/expenses rejects amount > 1 billion."""
        response = client.post(
            "/api/expenses", json={"name": "Big", "amount": 1_000_000_001}
        )
        assert response.status_code == 400

    def test_settings_no_body(self, client):
        """PUT /api/settings with no body returns 400."""
        response = client.put("/api/settings", content_type="application/json")
        assert response.status_code == 400


class TestHealth:
    """Tests for health endpoint."""

    def test_health_check(self, client):
        """Health check returns ok status."""
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json == {"status": "ok"}


class TestSettings:
    """Tests for settings endpoints."""

    def test_get_settings_creates_default(self, client):
        """GET /api/settings creates default settings if none exist."""
        response = client.get("/api/settings")
        assert response.status_code == 200
        data = response.json
        assert data["tax_percentage"] == 25.0
        assert "updated_at" in data

    def test_update_settings(self, client):
        """PUT /api/settings updates tax percentage."""
        response = client.put("/api/settings", json={"tax_percentage": 30.5})
        assert response.status_code == 200
        data = response.json
        assert data["tax_percentage"] == 30.5

    def test_update_settings_validation(self, client):
        """PUT /api/settings validates tax percentage."""
        response = client.put("/api/settings", json={"tax_percentage": 150})
        assert response.status_code == 400

        response = client.put("/api/settings", json={"tax_percentage": -5})
        assert response.status_code == 400


class TestAccounts:
    """Tests for account endpoints."""

    def test_list_accounts_empty(self, client):
        """GET /api/accounts returns empty list initially."""
        response = client.get("/api/accounts")
        assert response.status_code == 200
        assert response.json == []

    def test_create_account(self, client):
        """POST /api/accounts creates new account."""
        response = client.post(
            "/api/accounts",
            json={"name": "Checking", "balance": 1000.50, "is_credit": False},
        )
        assert response.status_code == 201
        data = response.json
        assert data["name"] == "Checking"
        assert data["balance"] == 1000.50
        assert data["is_credit"] is False
        assert "id" in data

    def test_update_account(self, client):
        """PUT /api/accounts/<id> updates account."""
        # Create account first
        create_response = client.post(
            "/api/accounts", json={"name": "Test", "balance": 100}
        )
        account_id = create_response.json["id"]

        # Update it
        response = client.put(
            f"/api/accounts/{account_id}",
            json={"name": "Updated", "balance": 200.00},
        )
        assert response.status_code == 200
        assert response.json["name"] == "Updated"
        assert response.json["balance"] == 200.00

    def test_delete_account(self, client):
        """DELETE /api/accounts/<id> removes account."""
        # Create account first
        create_response = client.post(
            "/api/accounts", json={"name": "ToDelete", "balance": 0}
        )
        account_id = create_response.json["id"]

        # Delete it
        response = client.delete(f"/api/accounts/{account_id}")
        assert response.status_code == 200

        # Verify it's gone
        list_response = client.get("/api/accounts")
        assert len(list_response.json) == 0

    def test_account_not_found(self, client):
        """PUT/DELETE return 404 for non-existent account."""
        response = client.put("/api/accounts/999", json={"name": "Test"})
        assert response.status_code == 404

        response = client.delete("/api/accounts/999")
        assert response.status_code == 404


class TestIncome:
    """Tests for income endpoints."""

    def test_list_income_empty(self, client):
        """GET /api/income returns empty list initially."""
        response = client.get("/api/income")
        assert response.status_code == 200
        assert response.json == []

    def test_create_income(self, client):
        """POST /api/income creates new income item."""
        response = client.post(
            "/api/income",
            json={"name": "Salary", "gross_amount": 5000.00, "is_taxed": True},
        )
        assert response.status_code == 201
        data = response.json
        assert data["name"] == "Salary"
        assert data["gross_amount"] == 5000.00
        assert data["is_taxed"] is True
        assert data["tax_percentage"] is None

    def test_create_income_with_custom_tax(self, client):
        """POST /api/income with custom tax percentage."""
        response = client.post(
            "/api/income",
            json={
                "name": "Lunch benefit",
                "gross_amount": 200.00,
                "is_taxed": True,
                "tax_percentage": 75.0,
            },
        )
        assert response.status_code == 201
        assert response.json["tax_percentage"] == 75.0

    def test_update_income(self, client):
        """PUT /api/income/<id> updates income item."""
        create_response = client.post(
            "/api/income", json={"name": "Test", "gross_amount": 100}
        )
        income_id = create_response.json["id"]

        response = client.put(
            f"/api/income/{income_id}",
            json={"name": "Updated", "gross_amount": 200.00},
        )
        assert response.status_code == 200
        assert response.json["name"] == "Updated"
        assert response.json["gross_amount"] == 200.00

    def test_delete_income(self, client):
        """DELETE /api/income/<id> removes income item."""
        create_response = client.post(
            "/api/income", json={"name": "ToDelete", "gross_amount": 0}
        )
        income_id = create_response.json["id"]

        response = client.delete(f"/api/income/{income_id}")
        assert response.status_code == 200

        list_response = client.get("/api/income")
        assert len(list_response.json) == 0


class TestExpenses:
    """Tests for expense endpoints."""

    def test_list_expenses_empty(self, client):
        """GET /api/expenses returns empty list initially."""
        response = client.get("/api/expenses")
        assert response.status_code == 200
        assert response.json == []

    def test_create_expense(self, client):
        """POST /api/expenses creates new expense item."""
        response = client.post(
            "/api/expenses",
            json={"name": "Rent", "amount": 1200.00},
        )
        assert response.status_code == 201
        data = response.json
        assert data["name"] == "Rent"
        assert data["amount"] == 1200.00

    def test_update_expense(self, client):
        """PUT /api/expenses/<id> updates expense item."""
        create_response = client.post(
            "/api/expenses", json={"name": "Test", "amount": 100}
        )
        expense_id = create_response.json["id"]

        response = client.put(
            f"/api/expenses/{expense_id}",
            json={"name": "Updated", "amount": 200.00},
        )
        assert response.status_code == 200
        assert response.json["name"] == "Updated"
        assert response.json["amount"] == 200.00

    def test_delete_expense(self, client):
        """DELETE /api/expenses/<id> removes expense item."""
        create_response = client.post(
            "/api/expenses", json={"name": "ToDelete", "amount": 0}
        )
        expense_id = create_response.json["id"]

        response = client.delete(f"/api/expenses/{expense_id}")
        assert response.status_code == 200

        list_response = client.get("/api/expenses")
        assert len(list_response.json) == 0


class TestBudget:
    """Tests for budget endpoint."""

    def test_get_budget_empty(self, client):
        """GET /api/budget/current returns empty budget."""
        response = client.get("/api/budget/current")
        assert response.status_code == 200
        data = response.json

        assert "settings" in data
        assert "income" in data
        assert "accounts" in data
        assert "expenses" in data
        assert "totals" in data

        assert data["income"] == []
        assert data["accounts"] == []
        assert data["expenses"] == []
        assert data["totals"]["gross_income"] == 0
        assert data["totals"]["net_income"] == 0
        assert data["totals"]["current_balance"] == 0
        assert data["totals"]["total_expenses"] == 0
        assert data["totals"]["net_position"] == 0

    def test_get_budget_with_seeded_data(self, seeded_client):
        """GET /api/budget/current returns correct calculations after seeding."""
        response = seeded_client.get("/api/budget/current")
        assert response.status_code == 200
        data = response.json

        # Check counts (5 income, 4 accounts, 9 expenses)
        assert len(data["income"]) == 5
        assert len(data["accounts"]) == 4
        assert len(data["expenses"]) == 9

        # Check settings
        assert data["settings"]["tax_percentage"] == 25.0
        assert data["settings"]["payday_day"] == 25

        # Check totals
        totals = data["totals"]

        # Gross income: 5000+300+200+1000 = 6500 (lunch benefit excluded)
        assert totals["gross_income"] == 6500.0

        # Net income calculation:
        # Salary: 5000 * 0.75 = 3750
        # Freelance: 300 * 0.75 = 225
        # Dividends: 200 (untaxed)
        # Year-end bonus: 1000 * 0.75 = 750
        # Lunch benefit: -200 * 0.75 = -150 (deduction)
        # Total: 3750 + 225 + 200 + 750 + (-150) = 4775
        assert totals["net_income"] == 4775.0

        # Current balance: 3500 + 8000 + (-750) + (-200) = 10550
        assert totals["current_balance"] == 10550.0

        # Total expenses: 1200+100+150+50+500+1200+50+150+800 = 4200
        assert totals["total_expenses"] == 4200.0

        # Net position: 10550 - 4200 = 6350
        assert totals["net_position"] == 6350.0

    def test_due_today_bill_auto_clears(self, client, monkeypatch):
        """A bill due today is assumed paid: it drops out of the 'before payday'
        totals, and stays on this period's list ticked off (so a debit that hasn't
        landed can be flagged) as well as showing up again next period.
        A bill due tomorrow is still counted as due."""
        import datetime

        from app.routes import budget as budget_route

        class _FixedDate(datetime.date):
            @classmethod
            def today(cls):
                return cls(2026, 6, 10)

        # Freeze "today" so the pay-period window is deterministic.
        # Default payday_day is 25, so the next payday is 2026-06-25.
        monkeypatch.setattr(budget_route, "date", _FixedDate)

        # Monthly bills, distinguished by due day relative to the frozen today.
        client.post(
            "/api/expenses", json={"name": "DueToday", "amount": 100, "due_day": 10}
        )
        client.post(
            "/api/expenses", json={"name": "DueTomorrow", "amount": 200, "due_day": 11}
        )
        client.post(
            "/api/expenses", json={"name": "DueLater", "amount": 300, "due_day": 20}
        )
        client.post(
            "/api/expenses",
            json={
                "name": "SaveToday",
                "amount": 50,
                "due_day": 10,
                "is_savings_goal": True,
            },
        )

        totals = client.get("/api/budget/current").json["totals"]

        # DueToday (100) auto-clears; only DueTomorrow + DueLater are still due.
        assert totals["expenses_before_payday"] == 500.0
        # Savings transfer due today auto-clears too.
        assert totals["savings_before_payday"] == 0.0

        before = {e["name"]: e for e in totals["expenses_before_payday_list"]}
        assert set(before) == {"DueToday", "DueTomorrow", "DueLater"}

        # DueToday stays listed as already settled; the others are still due.
        assert before["DueToday"]["is_settled"] is True
        assert before["DueTomorrow"]["is_settled"] is False
        assert before["DueLater"]["is_settled"] is False

        # Each is its own item's nearest occurrence, so each can be corrected.
        assert all(e["can_settle"] is True for e in before.values())

        # The due-today bill isn't lost: its next occurrence shows in the next
        # period, and it must NOT be misrouted into the "future" bucket.
        next_names = {e["name"] for e in totals["expenses_next_period_list"]}
        future_names = {e["name"] for e in totals["expenses_future_list"]}
        assert "DueToday" in next_names
        assert "DueToday" not in future_names

    def test_one_time_bill_due_today_clears(self, client, monkeypatch):
        """A one-time bill due exactly today stops counting as due, and is listed
        only as this period's settled item (regression guard: it must not land in
        the 'next period' or 'future' buckets)."""
        import datetime

        from app.routes import budget as budget_route

        class _FixedDate(datetime.date):
            @classmethod
            def today(cls):
                return cls(2026, 6, 10)

        monkeypatch.setattr(budget_route, "date", _FixedDate)

        client.post(
            "/api/expenses",
            json={
                "name": "OneTimeToday",
                "amount": 99,
                "is_ephemeral": True,
                "start_date": "2026-06-10",
                "due_day": 10,
            },
        )

        totals = client.get("/api/budget/current").json["totals"]

        assert totals["expenses_before_payday"] == 0.0

        before = totals["expenses_before_payday_list"]
        assert [e["name"] for e in before] == ["OneTimeToday"]
        assert before[0]["is_settled"] is True

        later = totals["expenses_next_period_list"] + totals["expenses_future_list"]
        assert all(e["name"] != "OneTimeToday" for e in later)


class TestOccurrenceOverrides:
    """Tests for marking a single occurrence paid/received early or still pending.

    Both corrections are one-offs: they move the money for one occurrence only
    and never touch the schedule, so every later occurrence still lands on its
    own day and the monthly rates behind the forecast stay put.

    Default payday_day is 25, so with today frozen to 2026-06-10 the current pay
    period runs 2026-05-25 -> 2026-06-25, and the next to 2026-07-25.
    """

    def freeze(self, monkeypatch, year, month, day):
        """Freeze today across every module that reads the clock."""
        import datetime

        from app.routes import budget as budget_route
        from app.routes import expenses as expenses_route
        from app.routes import income as income_route

        class _FixedDate(datetime.date):
            @classmethod
            def today(cls):
                return cls(year, month, day)

        for module in (budget_route, expenses_route, income_route):
            monkeypatch.setattr(module, "date", _FixedDate)

    def settle(self, client, path, item_id, occurrence_date, settled):
        return client.put(
            f"/api/{path}/{item_id}/occurrence",
            json={"occurrence_date": occurrence_date, "settled": settled},
        )

    def test_bill_paid_early_skips_only_that_occurrence(self, client, monkeypatch):
        """Marking the next occurrence paid drops it from what's still due, and
        leaves the following month's occurrence and the monthly rate alone."""
        self.freeze(monkeypatch, 2026, 6, 10)

        expense_id = client.post(
            "/api/expenses", json={"name": "Rent", "amount": 300, "due_day": 20}
        ).json["id"]

        totals = client.get("/api/budget/current").json["totals"]
        assert totals["expenses_before_payday"] == 300.0
        assert totals["expenses_next_period"] == 300.0

        response = self.settle(client, "expenses", expense_id, "2026-06-20", True)
        assert response.status_code == 200
        assert response.json["settled_occurrence"] == "2026-06-20"

        totals = client.get("/api/budget/current").json["totals"]
        assert totals["expenses_before_payday"] == 0.0
        # The n+1 occurrence and the forecast rate are untouched.
        assert totals["expenses_next_period"] == 300.0
        assert totals["monthly_expenses"] == 300.0

        row = totals["expenses_before_payday_list"][0]
        assert row["next_occurrence_date"] == "2026-06-20"
        assert row["is_settled"] is True

    def test_bill_paid_early_can_be_undone(self, client, monkeypatch):
        """Un-ticking a bill marked paid early puts it back on the books."""
        self.freeze(monkeypatch, 2026, 6, 10)

        expense_id = client.post(
            "/api/expenses", json={"name": "Rent", "amount": 300, "due_day": 20}
        ).json["id"]

        self.settle(client, "expenses", expense_id, "2026-06-20", True)
        response = self.settle(client, "expenses", expense_id, "2026-06-20", False)
        assert response.status_code == 200
        assert response.json["settled_occurrence"] is None

        totals = client.get("/api/budget/current").json["totals"]
        assert totals["expenses_before_payday"] == 300.0

    def test_bill_not_debited_yet_keeps_counting(self, client, monkeypatch):
        """A bill whose due day fell on a weekend can be flagged as not paid, and
        then still counts as due even though its day has passed."""
        self.freeze(monkeypatch, 2026, 6, 10)

        expense_id = client.post(
            "/api/expenses", json={"name": "Loan", "amount": 250, "due_day": 10}
        ).json["id"]

        # Auto-cleared on its due day by default.
        totals = client.get("/api/budget/current").json["totals"]
        assert totals["expenses_before_payday"] == 0.0

        response = self.settle(client, "expenses", expense_id, "2026-06-10", False)
        assert response.status_code == 200
        assert response.json["pending_occurrence"] == "2026-06-10"

        totals = client.get("/api/budget/current").json["totals"]
        assert totals["expenses_before_payday"] == 250.0
        assert totals["expenses_next_period"] == 250.0
        assert totals["monthly_expenses"] == 250.0

        row = totals["expenses_before_payday_list"][0]
        assert row["next_occurrence_date"] == "2026-06-10"
        assert row["is_settled"] is False

    def test_bill_still_pending_after_its_day(self, client, monkeypatch):
        """The pending mark outlives its own due day — that is the point — so a
        Saturday bill debited on Monday keeps showing until it is ticked off."""
        self.freeze(monkeypatch, 2026, 6, 10)
        expense_id = client.post(
            "/api/expenses", json={"name": "Loan", "amount": 250, "due_day": 10}
        ).json["id"]
        self.settle(client, "expenses", expense_id, "2026-06-10", False)

        self.freeze(monkeypatch, 2026, 6, 12)
        totals = client.get("/api/budget/current").json["totals"]
        assert totals["expenses_before_payday"] == 250.0

        # Ticking it off once the debit lands clears the mark.
        response = self.settle(client, "expenses", expense_id, "2026-06-10", True)
        assert response.status_code == 200
        assert response.json["pending_occurrence"] is None

        totals = client.get("/api/budget/current").json["totals"]
        assert totals["expenses_before_payday"] == 0.0

    def test_settled_mark_expires_on_its_day(self, client, monkeypatch):
        """Once the settled occurrence's day arrives the default assumption says
        the same thing, so the mark is dropped rather than left to linger."""
        self.freeze(monkeypatch, 2026, 6, 10)
        expense_id = client.post(
            "/api/expenses", json={"name": "Rent", "amount": 300, "due_day": 20}
        ).json["id"]
        self.settle(client, "expenses", expense_id, "2026-06-20", True)

        self.freeze(monkeypatch, 2026, 6, 21)
        client.get("/api/budget/current")

        expense = client.get("/api/expenses").json[0]
        assert expense["settled_occurrence"] is None

    def test_pending_mark_expires_when_superseded(self, client, monkeypatch):
        """A pending mark is scoped to the current pay period: once a newer
        occurrence has come due it refers to closed history and is dropped."""
        self.freeze(monkeypatch, 2026, 6, 10)
        expense_id = client.post(
            "/api/expenses", json={"name": "Loan", "amount": 250, "due_day": 10}
        ).json["id"]
        self.settle(client, "expenses", expense_id, "2026-06-10", False)

        self.freeze(monkeypatch, 2026, 7, 10)
        totals = client.get("/api/budget/current").json["totals"]

        assert client.get("/api/expenses").json[0]["pending_occurrence"] is None
        assert totals["expenses_before_payday"] == 0.0

    def test_pending_one_time_bill_is_not_archived(self, client, monkeypatch):
        """A one-time bill flagged as not debited yet survives the auto-archive:
        its money hasn't moved, so it isn't history."""
        self.freeze(monkeypatch, 2026, 6, 10)
        expense_id = client.post(
            "/api/expenses",
            json={
                "name": "TaxBill",
                "amount": 400,
                "is_ephemeral": True,
                "start_date": "2026-06-10",
                "due_day": 10,
            },
        ).json["id"]
        self.settle(client, "expenses", expense_id, "2026-06-10", False)

        self.freeze(monkeypatch, 2026, 6, 15)
        data = client.get("/api/budget/current").json

        assert [e["name"] for e in data["expenses"]] == ["TaxBill"]
        assert data["archived_expenses"] == []
        assert data["totals"]["expenses_before_payday"] == 400.0

        # It is charged against the roadmap as falling due now, not in the past.
        roadmap = client.get("/api/goals/roadmap").json
        assert roadmap["pending_one_time_net"] == -400.0

        # Come the next pay period it is stale either way, and archives as usual.
        self.freeze(monkeypatch, 2026, 6, 26)
        data = client.get("/api/budget/current").json
        assert [e["name"] for e in data["archived_expenses"]] == ["TaxBill"]

    def test_income_received_early(self, client, monkeypatch):
        """Pay that landed before payday is already in the balance, so it stops
        being counted as still to arrive."""
        self.freeze(monkeypatch, 2026, 6, 10)

        income_id = client.post(
            "/api/income",
            json={"name": "Salary", "gross_amount": 4000, "due_day": 25},
        ).json["id"]

        data = client.get("/api/budget/current").json
        assert data["totals"]["income_before_payday"] == 3000.0
        assert data["income"][0]["next_occurrence_date"] == "2026-06-25"
        assert data["income"][0]["is_settled"] is False

        response = self.settle(client, "income", income_id, "2026-06-25", True)
        assert response.status_code == 200

        data = client.get("/api/budget/current").json
        assert data["totals"]["income_before_payday"] == 0.0
        assert data["income"][0]["is_settled"] is True
        # Next month's paycheck and the monthly rate are unaffected.
        assert data["totals"]["income_next_period"] == 3000.0
        assert data["totals"]["monthly_net_income"] == 3000.0

    def test_income_not_received_yet(self, client, monkeypatch):
        """Pay that hasn't landed on its day still counts as incoming."""
        self.freeze(monkeypatch, 2026, 6, 10)

        income_id = client.post(
            "/api/income",
            json={"name": "Freelance", "gross_amount": 1000, "due_day": 5},
        ).json["id"]

        data = client.get("/api/budget/current").json
        # The 5th has passed, so by default it is assumed to be in the balance.
        assert data["totals"]["income_before_payday"] == 0.0
        assert data["income"][0]["next_occurrence_date"] == "2026-06-05"
        assert data["income"][0]["is_settled"] is True

        response = self.settle(client, "income", income_id, "2026-06-05", False)
        assert response.status_code == 200

        data = client.get("/api/budget/current").json
        assert data["totals"]["income_before_payday"] == 750.0
        assert data["income"][0]["is_settled"] is False

    def test_income_due_today_is_still_expected(self, client, monkeypatch):
        """Pay dated today has not been assumed into the balance (only payday
        itself is), so it shows as still expected and the tick box agrees with
        the total rather than contradicting it."""
        self.freeze(monkeypatch, 2026, 6, 10)

        income_id = client.post(
            "/api/income",
            json={"name": "Rent income", "gross_amount": 1000, "due_day": 10},
        ).json["id"]

        data = client.get("/api/budget/current").json
        assert data["totals"]["income_before_payday"] == 750.0
        assert data["income"][0]["next_occurrence_date"] == "2026-06-10"
        assert data["income"][0]["is_settled"] is False

        response = self.settle(client, "income", income_id, "2026-06-10", True)
        assert response.status_code == 200

        data = client.get("/api/budget/current").json
        assert data["totals"]["income_before_payday"] == 0.0
        assert data["income"][0]["is_settled"] is True

    def test_only_the_nearest_occurrences_can_be_overridden(self, client, monkeypatch):
        """A weekly bill occurs several times before payday, but only the two
        around today can be marked — the one just gone by (did it debit?) and the
        next one up (paid early?). Later ones are a schedule change, not a timing
        fix."""
        self.freeze(monkeypatch, 2026, 6, 10)

        expense_id = client.post(
            "/api/expenses",
            json={
                "name": "Weekly",
                "amount": 50,
                "frequency_value": 1,
                "frequency_unit": "weeks",
                "start_date": "2026-06-03",
                "due_day": 3,
            },
        ).json["id"]

        rows = client.get("/api/budget/current").json["totals"][
            "expenses_before_payday_list"
        ]
        settleable = [r["next_occurrence_date"] for r in rows if r["can_settle"]]
        assert settleable == ["2026-06-10", "2026-06-17"]
        assert "2026-06-24" in [r["next_occurrence_date"] for r in rows]

        response = self.settle(client, "expenses", expense_id, "2026-06-24", True)
        assert response.status_code == 400
        assert "occurrence" in response.json["error"]

    def test_weekly_item_without_a_start_date_ticks_off_a_listed_occurrence(
        self, client, monkeypatch
    ):
        """A day/week cadence with no start_date takes its phase from the window
        it is generated in, so the tick box has to be resolved against the same
        window as the list — otherwise it lands on a date that isn't shown."""
        self.freeze(monkeypatch, 2026, 6, 10)

        expense_id = client.post(
            "/api/expenses",
            json={
                "name": "Groceries",
                "amount": 80,
                "frequency_value": 1,
                "frequency_unit": "weeks",
                "due_day": 10,
            },
        ).json["id"]

        rows = client.get("/api/budget/current").json["totals"][
            "expenses_before_payday_list"
        ]
        upcoming = [r for r in rows if not r["is_settled"]]
        assert upcoming[0]["can_settle"] is True

        response = self.settle(
            client, "expenses", expense_id, upcoming[0]["next_occurrence_date"], True
        )
        assert response.status_code == 200

    def test_occurrence_validation(self, client, monkeypatch):
        """Bad requests are rejected rather than silently stored."""
        self.freeze(monkeypatch, 2026, 6, 10)

        expense_id = client.post(
            "/api/expenses", json={"name": "Rent", "amount": 300, "due_day": 20}
        ).json["id"]

        assert (
            self.settle(client, "expenses", 999, "2026-06-20", True).status_code == 404
        )
        assert (
            self.settle(client, "expenses", expense_id, "not-a-date", True).status_code
            == 400
        )
        assert (
            client.put(
                f"/api/expenses/{expense_id}/occurrence", json={"settled": True}
            ).status_code
            == 400
        )
        assert (
            client.put(
                f"/api/expenses/{expense_id}/occurrence",
                json={"occurrence_date": "2026-06-20"},
            ).status_code
            == 400
        )
        assert self.settle(client, "income", 999, "2026-06-25", True).status_code == 404


class TestSeed:
    """Tests for seed endpoint."""

    def test_seed_creates_data(self, client):
        """POST /api/seed creates example data."""
        response = client.post("/api/seed")
        assert response.status_code == 200
        data = response.json

        assert data["message"] == "Example data seeded successfully"
        assert data["counts"]["settings"] == 1
        assert data["counts"]["income_items"] == 5
        assert data["counts"]["accounts"] == 4
        assert data["counts"]["expenses"] == 9
        assert data["counts"]["goals"] == 3

    def test_seed_is_idempotent(self, client):
        """POST /api/seed clears and recreates data."""
        # Seed twice
        client.post("/api/seed")
        response = client.post("/api/seed")
        assert response.status_code == 200

        # Should still have same counts (not doubled)
        budget_response = client.get("/api/budget/current")
        data = budget_response.json
        assert len(data["income"]) == 5
        assert len(data["accounts"]) == 4
        assert len(data["expenses"]) == 9


class TestNetIncomeCalculation:
    """Tests for net income calculation logic."""

    def test_untaxed_income(self, client):
        """Untaxed income is not reduced by tax."""
        # Set tax percentage
        client.put("/api/settings", json={"tax_percentage": 25.0})

        # Create untaxed income
        client.post(
            "/api/income",
            json={"name": "Gift", "gross_amount": 1000.00, "is_taxed": False},
        )

        response = client.get("/api/budget/current")
        totals = response.json["totals"]

        # Should be 1000 (no tax applied)
        assert totals["gross_income"] == 1000.0
        assert totals["net_income"] == 1000.0

    def test_taxed_income_default_rate(self, client):
        """Taxed income uses default tax rate."""
        client.put("/api/settings", json={"tax_percentage": 20.0})

        client.post(
            "/api/income",
            json={"name": "Salary", "gross_amount": 1000.00, "is_taxed": True},
        )

        response = client.get("/api/budget/current")
        totals = response.json["totals"]

        # Net = 1000 * (1 - 0.20) = 800
        assert totals["gross_income"] == 1000.0
        assert totals["net_income"] == 800.0

    def test_deduction_income(self, client):
        """Income marked as deduction is treated as a deduction."""
        client.put("/api/settings", json={"tax_percentage": 20.0})

        # Lunch benefit with 75% deduction rate
        # In Finland, lunch benefit is deducted from pay at 75% of value
        client.post(
            "/api/income",
            json={
                "name": "Lunch benefit",
                "gross_amount": 200.00,
                "is_taxed": True,
                "tax_percentage": 75.0,
                "is_deduction": True,
            },
        )

        response = client.get("/api/budget/current")
        totals = response.json["totals"]

        # Net = -200 * 0.75 = -150 (deduction from pay)
        # Gross = 0 (deductions are excluded from gross income)
        assert totals["gross_income"] == 0.0
        assert totals["net_income"] == -150.0


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_account_negative_balance(self, client):
        """Accounts can have negative balances (credit cards)."""
        response = client.post(
            "/api/accounts",
            json={"name": "Credit Card", "balance": -500, "is_credit": True},
        )
        assert response.status_code == 201
        assert response.json["balance"] == -500.0

    def test_account_zero_balance(self, client):
        """Accounts can have zero balance."""
        response = client.post("/api/accounts", json={"name": "Empty", "balance": 0})
        assert response.status_code == 201
        assert response.json["balance"] == 0.0

    def test_account_decimal_precision(self, client):
        """Account balances preserve decimal precision."""
        response = client.post(
            "/api/accounts", json={"name": "Precise", "balance": 1234.56}
        )
        assert response.status_code == 201
        assert response.json["balance"] == 1234.56

    def test_income_zero_amount(self, client):
        """Income items can have zero amount."""
        response = client.post(
            "/api/income", json={"name": "Placeholder", "gross_amount": 0}
        )
        assert response.status_code == 201
        assert response.json["gross_amount"] == 0.0

    def test_expense_zero_amount(self, client):
        """Expense items can have zero amount."""
        response = client.post("/api/expenses", json={"name": "Free", "amount": 0})
        assert response.status_code == 201
        assert response.json["amount"] == 0.0

    def test_budget_totals_with_negative_balance(self, client):
        """Budget totals correctly include negative account balances."""
        client.post("/api/accounts", json={"name": "Checking", "balance": 1000})
        client.post(
            "/api/accounts",
            json={"name": "Credit Card", "balance": -300, "is_credit": True},
        )

        response = client.get("/api/budget/current")
        assert response.json["totals"]["current_balance"] == 700.0

    def test_budget_totals_all_negative(self, client):
        """Budget handles all-negative account balances."""
        client.post(
            "/api/accounts",
            json={"name": "Credit Card 1", "balance": -500, "is_credit": True},
        )
        client.post(
            "/api/accounts",
            json={"name": "Credit Card 2", "balance": -300, "is_credit": True},
        )

        response = client.get("/api/budget/current")
        assert response.json["totals"]["current_balance"] == -800.0

    def test_net_position_negative(self, client):
        """Net position can be negative (expenses > balance)."""
        client.post("/api/accounts", json={"name": "Checking", "balance": 500})
        client.post("/api/expenses", json={"name": "Rent", "amount": 1200})

        response = client.get("/api/budget/current")
        # Net position = 500 - 1200 = -700
        assert response.json["totals"]["net_position"] == -700.0

    def test_partial_update_account(self, client):
        """PUT /api/accounts/<id> with partial data preserves other fields."""
        create_response = client.post(
            "/api/accounts",
            json={"name": "Test", "balance": 1000, "is_credit": True},
        )
        account_id = create_response.json["id"]

        # Update only balance
        response = client.put(f"/api/accounts/{account_id}", json={"balance": 2000})
        assert response.status_code == 200
        assert response.json["balance"] == 2000.0
        assert response.json["name"] == "Test"  # Preserved
        assert response.json["is_credit"] is True  # Preserved

    def test_partial_update_income(self, client):
        """PUT /api/income/<id> with partial data preserves other fields."""
        create_response = client.post(
            "/api/income",
            json={"name": "Salary", "gross_amount": 5000, "is_taxed": True},
        )
        income_id = create_response.json["id"]

        response = client.put(f"/api/income/{income_id}", json={"gross_amount": 6000})
        assert response.status_code == 200
        assert response.json["gross_amount"] == 6000.0
        assert response.json["name"] == "Salary"
        assert response.json["is_taxed"] is True

    def test_partial_update_expense(self, client):
        """PUT /api/expenses/<id> with partial data preserves other fields."""
        create_response = client.post(
            "/api/expenses",
            json={"name": "Rent", "amount": 1200, "is_savings_goal": False},
        )
        expense_id = create_response.json["id"]

        response = client.put(f"/api/expenses/{expense_id}", json={"amount": 1300})
        assert response.status_code == 200
        assert response.json["amount"] == 1300.0
        assert response.json["name"] == "Rent"

    def test_tax_percentage_boundary_values(self, client):
        """Tax percentage accepts boundary values 0 and 100."""
        response = client.put("/api/settings", json={"tax_percentage": 0})
        assert response.status_code == 200
        assert response.json["tax_percentage"] == 0.0

        response = client.put("/api/settings", json={"tax_percentage": 100})
        assert response.status_code == 200
        assert response.json["tax_percentage"] == 100.0

    def test_net_income_zero_tax(self, client):
        """Net income equals gross when tax is 0%."""
        client.put("/api/settings", json={"tax_percentage": 0})
        client.post(
            "/api/income",
            json={"name": "Salary", "gross_amount": 5000, "is_taxed": True},
        )

        response = client.get("/api/budget/current")
        assert response.json["totals"]["gross_income"] == 5000.0
        assert response.json["totals"]["net_income"] == 5000.0

    def test_net_income_100_percent_tax(self, client):
        """Net income is 0 when tax is 100%."""
        client.put("/api/settings", json={"tax_percentage": 100})
        client.post(
            "/api/income",
            json={"name": "Salary", "gross_amount": 5000, "is_taxed": True},
        )

        response = client.get("/api/budget/current")
        assert response.json["totals"]["gross_income"] == 5000.0
        assert response.json["totals"]["net_income"] == 0.0

    def test_income_not_found(self, client):
        """PUT/DELETE return 404 for non-existent income."""
        response = client.put("/api/income/999", json={"name": "Test"})
        assert response.status_code == 404

        response = client.delete("/api/income/999")
        assert response.status_code == 404

    def test_expense_not_found(self, client):
        """PUT/DELETE return 404 for non-existent expense."""
        response = client.put("/api/expenses/999", json={"name": "Test"})
        assert response.status_code == 404

        response = client.delete("/api/expenses/999")
        assert response.status_code == 404

    def test_update_account_validates_balance(self, client):
        """PUT /api/accounts/<id> validates balance."""
        create_response = client.post(
            "/api/accounts", json={"name": "Test", "balance": 100}
        )
        account_id = create_response.json["id"]

        response = client.put(
            f"/api/accounts/{account_id}", json={"balance": 1_000_000_001}
        )
        assert response.status_code == 400

    def test_update_account_validates_name(self, client):
        """PUT /api/accounts/<id> validates name."""
        create_response = client.post(
            "/api/accounts", json={"name": "Test", "balance": 100}
        )
        account_id = create_response.json["id"]

        response = client.put(f"/api/accounts/{account_id}", json={"name": "x" * 101})
        assert response.status_code == 400

    def test_savings_goal_flag(self, client):
        """Expenses can be marked as savings goals."""
        response = client.post(
            "/api/expenses",
            json={"name": "Emergency Fund", "amount": 500, "is_savings_goal": True},
        )
        assert response.status_code == 201
        assert response.json["is_savings_goal"] is True

    def test_deduction_flag(self, client):
        """Income can be marked as deduction."""
        response = client.post(
            "/api/income",
            json={
                "name": "Lunch",
                "gross_amount": 200,
                "is_taxed": True,
                "is_deduction": True,
                "tax_percentage": 75,
            },
        )
        assert response.status_code == 201
        assert response.json["is_deduction"] is True


class TestMonthlyNormalization:
    """Tests for frequency-normalized monthly totals."""

    def test_monthly_rates_normalize_frequencies(self, client):
        """Quarterly/yearly bills count at a fraction; one-time items excluded."""
        client.post(
            "/api/income",
            json={"name": "Salary", "gross_amount": 4000, "is_taxed": False},
        )
        client.post("/api/expenses", json={"name": "Rent", "amount": 1000})
        client.post(
            "/api/expenses",
            json={
                "name": "Water",
                "amount": 90,
                "frequency_value": 3,
                "frequency_unit": "months",
            },
        )
        client.post(
            "/api/expenses",
            json={
                "name": "Insurance",
                "amount": 120,
                "frequency_value": 1,
                "frequency_unit": "years",
            },
        )
        client.post(
            "/api/expenses",
            json={
                "name": "One-time tax",
                "amount": 500,
                "is_ephemeral": True,
                "start_date": "2099-01-01",
            },
        )

        totals = client.get("/api/budget/current").json["totals"]

        # 1000 + 90/3 + 120/12 = 1040; the one-time 500 is excluded
        assert totals["monthly_expenses"] == pytest.approx(1040.0)
        assert totals["monthly_net_income"] == pytest.approx(4000.0)
        assert totals["monthly_surplus"] == pytest.approx(2960.0)
        # Face-value total still counts every line once
        assert totals["total_expenses"] == 1710.0

    def test_weekly_items_normalize_up(self, client):
        """A weekly bill counts ~4.35 times per month."""
        client.post(
            "/api/expenses",
            json={
                "name": "Groceries",
                "amount": 70,
                "frequency_value": 1,
                "frequency_unit": "weeks",
            },
        )

        totals = client.get("/api/budget/current").json["totals"]
        # 70 * 30.4375/7 = 304.375
        assert totals["monthly_expenses"] == pytest.approx(304.375)
