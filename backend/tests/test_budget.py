"""Tests for budget API endpoints."""


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

        # Check counts
        assert len(data["income"]) == 3
        assert len(data["accounts"]) == 3
        assert len(data["expenses"]) == 6

        # Check settings
        assert data["settings"]["tax_percentage"] == 25.0

        # Check totals
        totals = data["totals"]

        # Gross income: 5000 + 500 = 5500 (lunch benefit excluded as deduction)
        assert totals["gross_income"] == 5500.0

        # Net income calculation:
        # Salary: 5000 * 0.75 = 3750
        # Side income: 500 * 0.75 = 375
        # Lunch benefit: -200 * 0.75 = -150 (deduction)
        # Total: 3750 + 375 + (-150) = 3975
        assert totals["net_income"] == 3975.0

        # Current balance: 3500 + 2000 + (-500) = 5000
        assert totals["current_balance"] == 5000.0

        # Total expenses: 1200 + 400 + 150 + 100 + 50 + 500 = 2400
        assert totals["total_expenses"] == 2400.0

        # Net position: 5000 - 2400 = 2600
        assert totals["net_position"] == 2600.0


class TestSeed:
    """Tests for seed endpoint."""

    def test_seed_creates_data(self, client):
        """POST /api/seed creates example data."""
        response = client.post("/api/seed")
        assert response.status_code == 200
        data = response.json

        assert data["message"] == "Example data seeded successfully"
        assert data["counts"]["settings"] == 1
        assert data["counts"]["income_items"] == 3
        assert data["counts"]["accounts"] == 3
        assert data["counts"]["expenses"] == 6

    def test_seed_is_idempotent(self, client):
        """POST /api/seed clears and recreates data."""
        # Seed twice
        client.post("/api/seed")
        response = client.post("/api/seed")
        assert response.status_code == 200

        # Should still have same counts (not doubled)
        budget_response = client.get("/api/budget/current")
        data = budget_response.json
        assert len(data["income"]) == 3
        assert len(data["accounts"]) == 3
        assert len(data["expenses"]) == 6


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
