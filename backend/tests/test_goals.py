"""Tests for goals API endpoints."""


class TestGoalValidation:
    """Tests for goal input validation."""

    def test_goal_missing_name(self, client):
        """POST /api/goals requires name."""
        response = client.post(
            "/api/goals",
            json={"goal_type": "net_worth", "target_value": 100000},
        )
        assert response.status_code == 400
        assert "name" in response.json["error"].lower()

    def test_goal_missing_goal_type(self, client):
        """POST /api/goals requires goal_type."""
        response = client.post(
            "/api/goals",
            json={"name": "Test Goal", "target_value": 100000},
        )
        assert response.status_code == 400
        assert "goal_type" in response.json["error"].lower()

    def test_goal_missing_target_value(self, client):
        """POST /api/goals requires target_value."""
        response = client.post(
            "/api/goals",
            json={"name": "Test Goal", "goal_type": "net_worth"},
        )
        assert response.status_code == 400
        assert "target_value" in response.json["error"].lower()

    def test_goal_invalid_goal_type(self, client):
        """POST /api/goals rejects invalid goal_type."""
        response = client.post(
            "/api/goals",
            json={
                "name": "Test Goal",
                "goal_type": "invalid_type",
                "target_value": 100000,
            },
        )
        assert response.status_code == 400
        assert "goal_type" in response.json["error"].lower()

    def test_goal_empty_name(self, client):
        """POST /api/goals rejects empty name."""
        response = client.post(
            "/api/goals",
            json={"name": "", "goal_type": "net_worth", "target_value": 100000},
        )
        assert response.status_code == 400

    def test_goal_name_too_long(self, client):
        """POST /api/goals rejects name > 100 chars."""
        response = client.post(
            "/api/goals",
            json={
                "name": "x" * 101,
                "goal_type": "net_worth",
                "target_value": 100000,
            },
        )
        assert response.status_code == 400

    def test_goal_target_value_exceeds_max(self, client):
        """POST /api/goals rejects target_value > 1 billion."""
        response = client.post(
            "/api/goals",
            json={
                "name": "Big Goal",
                "goal_type": "net_worth",
                "target_value": 1_000_000_001,
            },
        )
        assert response.status_code == 400

    def test_goal_savings_rate_exceeds_100(self, client):
        """POST /api/goals rejects savings_rate > 100%."""
        response = client.post(
            "/api/goals",
            json={
                "name": "Save Too Much",
                "goal_type": "savings_rate",
                "target_value": 101,
            },
        )
        assert response.status_code == 400

    def test_goal_savings_rate_negative(self, client):
        """POST /api/goals rejects negative savings_rate."""
        response = client.post(
            "/api/goals",
            json={
                "name": "Negative Savings",
                "goal_type": "savings_rate",
                "target_value": -10,
            },
        )
        assert response.status_code == 400

    def test_goal_no_body(self, client):
        """POST /api/goals with no body returns 400."""
        response = client.post("/api/goals", content_type="application/json")
        assert response.status_code == 400

    def test_goal_invalid_target_date(self, client):
        """POST /api/goals rejects invalid date format."""
        response = client.post(
            "/api/goals",
            json={
                "name": "Test Goal",
                "goal_type": "net_worth",
                "target_value": 100000,
                "target_date": "not-a-date",
            },
        )
        assert response.status_code == 400


class TestGoalCRUD:
    """Tests for goal CRUD operations."""

    def test_create_net_worth_goal(self, client):
        """POST /api/goals creates a net worth goal."""
        response = client.post(
            "/api/goals",
            json={
                "name": "100k Net Worth",
                "goal_type": "net_worth",
                "target_value": 100000,
            },
        )
        assert response.status_code == 201
        data = response.json
        assert data["name"] == "100k Net Worth"
        assert data["goal_type"] == "net_worth"
        assert data["target_value"] == 100000
        assert data["is_active"] is True
        assert data["target_date"] is None
        assert "id" in data
        assert "created_at" in data

    def test_create_savings_rate_goal(self, client):
        """POST /api/goals creates a savings rate goal."""
        response = client.post(
            "/api/goals",
            json={
                "name": "30% Savings Rate",
                "goal_type": "savings_rate",
                "target_value": 30,
            },
        )
        assert response.status_code == 201
        data = response.json
        assert data["goal_type"] == "savings_rate"
        assert data["target_value"] == 30

    def test_create_monthly_savings_goal(self, client):
        """POST /api/goals creates a monthly savings goal."""
        response = client.post(
            "/api/goals",
            json={
                "name": "Save 500€/month",
                "goal_type": "monthly_savings",
                "target_value": 500,
            },
        )
        assert response.status_code == 201
        data = response.json
        assert data["goal_type"] == "monthly_savings"
        assert data["target_value"] == 500

    def test_create_goal_with_target_date(self, client):
        """POST /api/goals with target_date."""
        response = client.post(
            "/api/goals",
            json={
                "name": "Goal with Date",
                "goal_type": "net_worth",
                "target_value": 50000,
                "target_date": "2025-12-31T00:00:00+00:00",
            },
        )
        assert response.status_code == 201
        data = response.json
        assert data["target_date"] is not None
        assert "2025-12-31" in data["target_date"]

    def test_create_inactive_goal(self, client):
        """POST /api/goals with is_active=False."""
        response = client.post(
            "/api/goals",
            json={
                "name": "Inactive Goal",
                "goal_type": "net_worth",
                "target_value": 10000,
                "is_active": False,
            },
        )
        assert response.status_code == 201
        assert response.json["is_active"] is False

    def test_list_goals_empty(self, client):
        """GET /api/goals returns empty list when no goals."""
        response = client.get("/api/goals")
        assert response.status_code == 200
        assert response.json == []

    def test_list_goals(self, client):
        """GET /api/goals returns all goals."""
        # Create multiple goals
        client.post(
            "/api/goals",
            json={
                "name": "Goal 1",
                "goal_type": "net_worth",
                "target_value": 10000,
            },
        )
        client.post(
            "/api/goals",
            json={
                "name": "Goal 2",
                "goal_type": "savings_rate",
                "target_value": 25,
            },
        )

        response = client.get("/api/goals")
        assert response.status_code == 200
        assert len(response.json) == 2

    def test_get_single_goal(self, client):
        """GET /api/goals/<id> returns specific goal."""
        create_response = client.post(
            "/api/goals",
            json={
                "name": "Test Goal",
                "goal_type": "net_worth",
                "target_value": 50000,
            },
        )
        goal_id = create_response.json["id"]

        response = client.get(f"/api/goals/{goal_id}")
        assert response.status_code == 200
        assert response.json["name"] == "Test Goal"
        assert response.json["id"] == goal_id

    def test_get_nonexistent_goal(self, client):
        """GET /api/goals/<id> returns 404 for nonexistent goal."""
        response = client.get("/api/goals/99999")
        assert response.status_code == 404

    def test_update_goal_name(self, client):
        """PUT /api/goals/<id> updates goal name."""
        create_response = client.post(
            "/api/goals",
            json={
                "name": "Original Name",
                "goal_type": "net_worth",
                "target_value": 50000,
            },
        )
        goal_id = create_response.json["id"]

        response = client.put(f"/api/goals/{goal_id}", json={"name": "New Name"})
        assert response.status_code == 200
        assert response.json["name"] == "New Name"

    def test_update_goal_target_value(self, client):
        """PUT /api/goals/<id> updates target_value."""
        create_response = client.post(
            "/api/goals",
            json={
                "name": "Test Goal",
                "goal_type": "net_worth",
                "target_value": 50000,
            },
        )
        goal_id = create_response.json["id"]

        response = client.put(f"/api/goals/{goal_id}", json={"target_value": 75000})
        assert response.status_code == 200
        assert response.json["target_value"] == 75000

    def test_update_goal_type(self, client):
        """PUT /api/goals/<id> updates goal_type."""
        create_response = client.post(
            "/api/goals",
            json={
                "name": "Test Goal",
                "goal_type": "net_worth",
                "target_value": 50,
            },
        )
        goal_id = create_response.json["id"]

        response = client.put(
            f"/api/goals/{goal_id}", json={"goal_type": "savings_rate"}
        )
        assert response.status_code == 200
        assert response.json["goal_type"] == "savings_rate"

    def test_update_goal_add_target_date(self, client):
        """PUT /api/goals/<id> adds target_date."""
        create_response = client.post(
            "/api/goals",
            json={
                "name": "Test Goal",
                "goal_type": "net_worth",
                "target_value": 50000,
            },
        )
        goal_id = create_response.json["id"]

        response = client.put(
            f"/api/goals/{goal_id}",
            json={"target_date": "2026-06-30T00:00:00+00:00"},
        )
        assert response.status_code == 200
        assert response.json["target_date"] is not None

    def test_update_goal_remove_target_date(self, client):
        """PUT /api/goals/<id> removes target_date."""
        create_response = client.post(
            "/api/goals",
            json={
                "name": "Test Goal",
                "goal_type": "net_worth",
                "target_value": 50000,
                "target_date": "2025-12-31T00:00:00+00:00",
            },
        )
        goal_id = create_response.json["id"]

        response = client.put(f"/api/goals/{goal_id}", json={"target_date": None})
        assert response.status_code == 200
        assert response.json["target_date"] is None

    def test_update_goal_deactivate(self, client):
        """PUT /api/goals/<id> deactivates goal."""
        create_response = client.post(
            "/api/goals",
            json={
                "name": "Test Goal",
                "goal_type": "net_worth",
                "target_value": 50000,
            },
        )
        goal_id = create_response.json["id"]

        response = client.put(f"/api/goals/{goal_id}", json={"is_active": False})
        assert response.status_code == 200
        assert response.json["is_active"] is False

    def test_update_nonexistent_goal(self, client):
        """PUT /api/goals/<id> returns 404 for nonexistent goal."""
        response = client.put("/api/goals/99999", json={"name": "New Name"})
        assert response.status_code == 404

    def test_update_goal_no_body(self, client):
        """PUT /api/goals/<id> with no body returns 400."""
        create_response = client.post(
            "/api/goals",
            json={
                "name": "Test Goal",
                "goal_type": "net_worth",
                "target_value": 50000,
            },
        )
        goal_id = create_response.json["id"]

        response = client.put(f"/api/goals/{goal_id}", content_type="application/json")
        assert response.status_code == 400

    def test_delete_goal(self, client):
        """DELETE /api/goals/<id> deletes goal."""
        create_response = client.post(
            "/api/goals",
            json={
                "name": "Test Goal",
                "goal_type": "net_worth",
                "target_value": 50000,
            },
        )
        goal_id = create_response.json["id"]

        response = client.delete(f"/api/goals/{goal_id}")
        assert response.status_code == 200

        # Verify it's deleted
        get_response = client.get(f"/api/goals/{goal_id}")
        assert get_response.status_code == 404

    def test_delete_nonexistent_goal(self, client):
        """DELETE /api/goals/<id> returns 404 for nonexistent goal."""
        response = client.delete("/api/goals/99999")
        assert response.status_code == 404


class TestGoalProgress:
    """Tests for goal progress calculation."""

    def test_progress_empty(self, client):
        """GET /api/goals/progress returns empty list when no active goals."""
        response = client.get("/api/goals/progress")
        assert response.status_code == 200
        assert response.json == []

    def test_progress_inactive_goals_excluded(self, client):
        """GET /api/goals/progress excludes inactive goals."""
        client.post(
            "/api/goals",
            json={
                "name": "Inactive Goal",
                "goal_type": "net_worth",
                "target_value": 100000,
                "is_active": False,
            },
        )

        response = client.get("/api/goals/progress")
        assert response.status_code == 200
        assert response.json == []

    def test_progress_net_worth_no_snapshot(self, client):
        """GET /api/goals/progress with net_worth goal but no snapshots."""
        client.post(
            "/api/goals",
            json={
                "name": "100k Goal",
                "goal_type": "net_worth",
                "target_value": 100000,
            },
        )

        response = client.get("/api/goals/progress")
        assert response.status_code == 200
        assert len(response.json) == 1

        progress = response.json[0]
        assert progress["current_value"] == 0
        assert progress["target_value"] == 100000
        assert progress["progress_percentage"] == 0
        assert progress["is_achieved"] is False
        assert progress["details"]["latest_month"] is None

    def test_progress_net_worth_with_snapshot(self, client):
        """GET /api/goals/progress with net_worth goal and snapshot data."""
        # First, seed categories and create a snapshot
        client.post("/api/networth/categories/seed")

        # Create a snapshot with net worth of 50000
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2025,
                "entries": [
                    {"category_id": 1, "amount": 60000},  # Cash asset
                    {"category_id": 11, "amount": -10000},  # Loan liability
                ],
            },
        )

        # Create goal
        client.post(
            "/api/goals",
            json={
                "name": "100k Goal",
                "goal_type": "net_worth",
                "target_value": 100000,
            },
        )

        response = client.get("/api/goals/progress")
        assert response.status_code == 200
        assert len(response.json) == 1

        progress = response.json[0]
        assert progress["current_value"] == 50000
        assert progress["target_value"] == 100000
        assert progress["progress_percentage"] == 50.0
        assert progress["is_achieved"] is False
        assert progress["details"]["latest_month"] == "2025-01"

    def test_progress_net_worth_achieved(self, client):
        """GET /api/goals/progress when net_worth goal is achieved."""
        client.post("/api/networth/categories/seed")

        # Create a snapshot with net worth of 120000
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2025,
                "entries": [
                    {"category_id": 1, "amount": 120000},
                ],
            },
        )

        client.post(
            "/api/goals",
            json={
                "name": "100k Goal",
                "goal_type": "net_worth",
                "target_value": 100000,
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        assert progress["current_value"] == 120000
        # Progress capped at 100%
        assert progress["progress_percentage"] == 100.0
        assert progress["is_achieved"] is True

    def test_progress_savings_rate_no_income(self, client):
        """GET /api/goals/progress with savings_rate but no income."""
        client.post(
            "/api/goals",
            json={
                "name": "30% Savings Rate",
                "goal_type": "savings_rate",
                "target_value": 30,
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        assert progress["current_value"] == 0
        assert progress["progress_percentage"] == 0
        assert progress["is_achieved"] is False

    def test_progress_savings_rate_with_income(self, client):
        """GET /api/goals/progress with savings_rate goal."""
        # Create income
        client.post(
            "/api/income",
            json={"name": "Salary", "gross_amount": 5000, "is_taxed": True},
        )

        # Create savings goal expense (is_savings_goal=True)
        client.post(
            "/api/expenses",
            json={"name": "Emergency Fund", "amount": 500, "is_savings_goal": True},
        )

        # Create savings rate goal
        client.post(
            "/api/goals",
            json={
                "name": "20% Savings Rate",
                "goal_type": "savings_rate",
                "target_value": 20,
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]

        # net_income = 5000 * 0.75 = 3750 (25% tax)
        # savings_rate = 500 / 3750 * 100 = 13.33%
        # progress = 13.33 / 20 * 100 = 66.67%
        assert progress["current_value"] > 0
        assert progress["target_value"] == 20
        assert progress["is_achieved"] is False
        assert "net_income" in progress["details"]
        assert "savings_amount" in progress["details"]

    def test_progress_monthly_savings_no_savings(self, client):
        """GET /api/goals/progress with monthly_savings but no savings goals."""
        client.post(
            "/api/goals",
            json={
                "name": "Save 500€",
                "goal_type": "monthly_savings",
                "target_value": 500,
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        assert progress["current_value"] == 0
        assert progress["progress_percentage"] == 0
        assert progress["is_achieved"] is False

    def test_progress_monthly_savings_with_savings(self, client):
        """GET /api/goals/progress with monthly_savings goal."""
        # Create savings goal expenses
        client.post(
            "/api/expenses",
            json={"name": "Emergency Fund", "amount": 300, "is_savings_goal": True},
        )
        client.post(
            "/api/expenses",
            json={"name": "Vacation Fund", "amount": 200, "is_savings_goal": True},
        )

        # Create monthly savings goal
        client.post(
            "/api/goals",
            json={
                "name": "Save 500€",
                "goal_type": "monthly_savings",
                "target_value": 500,
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        assert progress["current_value"] == 500
        assert progress["target_value"] == 500
        assert progress["progress_percentage"] == 100.0
        assert progress["is_achieved"] is True

    def test_progress_multiple_goals(self, client):
        """GET /api/goals/progress returns progress for all active goals."""
        client.post(
            "/api/goals",
            json={
                "name": "Net Worth Goal",
                "goal_type": "net_worth",
                "target_value": 100000,
            },
        )
        client.post(
            "/api/goals",
            json={
                "name": "Savings Rate Goal",
                "goal_type": "savings_rate",
                "target_value": 30,
            },
        )
        client.post(
            "/api/goals",
            json={
                "name": "Monthly Savings Goal",
                "goal_type": "monthly_savings",
                "target_value": 500,
            },
        )

        response = client.get("/api/goals/progress")
        assert response.status_code == 200
        assert len(response.json) == 3

        # Each should have required fields
        for progress in response.json:
            assert "goal" in progress
            assert "current_value" in progress
            assert "target_value" in progress
            assert "progress_percentage" in progress
            assert "is_achieved" in progress
            assert "details" in progress

    def test_progress_uses_latest_snapshot(self, client):
        """GET /api/goals/progress uses the most recent snapshot."""
        client.post("/api/networth/categories/seed")

        # Create older snapshot
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [{"category_id": 1, "amount": 30000}],
            },
        )

        # Create newer snapshot
        client.post(
            "/api/networth",
            json={
                "month": 6,
                "year": 2024,
                "entries": [{"category_id": 1, "amount": 50000}],
            },
        )

        client.post(
            "/api/goals",
            json={
                "name": "100k Goal",
                "goal_type": "net_worth",
                "target_value": 100000,
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        # Should use June 2024 (50000), not January (30000)
        assert progress["current_value"] == 50000
        assert progress["details"]["latest_month"] == "2024-06"
