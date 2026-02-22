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
            json={
                "name": "",
                "goal_type": "net_worth",
                "target_value": 100000,
            },
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

    def test_goal_negative_target_value(self, client):
        """POST /api/goals rejects negative target_value."""
        response = client.post(
            "/api/goals",
            json={
                "name": "Negative Goal",
                "goal_type": "net_worth",
                "target_value": -100,
            },
        )
        assert response.status_code == 400

    def test_savings_rate_exceeds_100(self, client):
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

    def test_savings_goal_requires_category_id(self, client):
        """POST /api/goals with savings_goal requires category_id."""
        response = client.post(
            "/api/goals",
            json={
                "name": "Vacation Fund",
                "goal_type": "savings_goal",
                "target_value": 5000,
            },
        )
        assert response.status_code == 400
        assert "category_id" in response.json["error"].lower()

    def test_nonexistent_category(self, client):
        """POST /api/goals with nonexistent category_id returns 404."""
        response = client.post(
            "/api/goals",
            json={
                "name": "Bad Category",
                "goal_type": "savings_goal",
                "target_value": 5000,
                "category_id": 99999,
            },
        )
        assert response.status_code == 404


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
        assert data["category_id"] is None
        assert "id" in data
        assert "created_at" in data

    def test_create_savings_rate_goal(self, client):
        """POST /api/goals creates a savings rate goal."""
        response = client.post(
            "/api/goals",
            json={
                "name": "Save 20% of income",
                "goal_type": "savings_rate",
                "target_value": 20,
            },
        )
        assert response.status_code == 201
        data = response.json
        assert data["goal_type"] == "savings_rate"
        assert data["target_value"] == 20
        assert data["category_id"] is None

    def test_create_savings_goal(self, client):
        """POST /api/goals creates a savings goal with category."""
        client.post("/api/networth/categories/seed")

        response = client.post(
            "/api/goals",
            json={
                "name": "Vacation Fund",
                "goal_type": "savings_goal",
                "target_value": 5000,
                "category_id": 1,
            },
        )
        assert response.status_code == 201
        data = response.json
        assert data["goal_type"] == "savings_goal"
        assert data["target_value"] == 5000
        assert data["category_id"] == 1

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
        client.post("/api/networth/categories/seed")

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
                "goal_type": "savings_goal",
                "target_value": 5000,
                "category_id": 1,
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

    def test_update_goal_category_id(self, client):
        """PUT /api/goals/<id> updates category_id."""
        client.post("/api/networth/categories/seed")

        create_response = client.post(
            "/api/goals",
            json={
                "name": "Savings Goal",
                "goal_type": "savings_goal",
                "target_value": 5000,
                "category_id": 1,
            },
        )
        goal_id = create_response.json["id"]

        response = client.put(f"/api/goals/{goal_id}", json={"category_id": 2})
        assert response.status_code == 200
        assert response.json["category_id"] == 2

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
        """GET /api/goals/progress with net_worth but no snapshots."""
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
        assert progress["data_months"] == 0

    def test_progress_net_worth_with_snapshot(self, client):
        """GET /api/goals/progress with net_worth and snapshot data."""
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

    def test_progress_net_worth_achieved(self, client):
        """GET /api/goals/progress when net_worth is achieved."""
        client.post("/api/networth/categories/seed")

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
                "name": "20% Savings Rate",
                "goal_type": "savings_rate",
                "target_value": 20,
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        # No income means 0 rate
        assert progress["current_value"] == 0
        assert progress["progress_percentage"] == 0
        assert progress["is_achieved"] is False

    def test_progress_savings_rate_with_income(self, client):
        """GET /api/goals/progress calculates savings rate correctly."""
        client.post("/api/networth/categories/seed")

        # Create income: 5000 gross, 25% tax = 3750 net
        client.post(
            "/api/income",
            json={"name": "Salary", "gross_amount": 5000, "is_taxed": True},
        )

        # Create snapshots showing 1000/month savings
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2025,
                "entries": [{"category_id": 1, "amount": 10000}],
            },
        )
        client.post(
            "/api/networth",
            json={
                "month": 2,
                "year": 2025,
                "entries": [{"category_id": 1, "amount": 11000}],  # +1000
            },
        )

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
        # 1000 / 3750 * 100 = 26.67%
        # progress = 26.67 / 20 * 100 = exceeds target
        assert 25 < progress["current_value"] < 28  # ~26.67%
        assert progress["target_value"] == 20
        assert progress["is_achieved"] is True  # 26.67% > 20%

    def test_progress_savings_goal_no_snapshot(self, client):
        """GET /api/goals/progress with savings_goal but no snapshots."""
        client.post("/api/networth/categories/seed")

        client.post(
            "/api/goals",
            json={
                "name": "Vacation Fund",
                "goal_type": "savings_goal",
                "target_value": 5000,
                "category_id": 1,
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        assert progress["current_value"] == 0
        assert progress["target_value"] == 5000
        assert progress["progress_percentage"] == 0
        assert progress["is_achieved"] is False

    def test_progress_savings_goal_with_snapshot(self, client):
        """GET /api/goals/progress with savings_goal and snapshot."""
        client.post("/api/networth/categories/seed")

        # Create snapshot with category 1 having 2500
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2025,
                "entries": [
                    {"category_id": 1, "amount": 2500},
                ],
            },
        )

        client.post(
            "/api/goals",
            json={
                "name": "Vacation Fund",
                "goal_type": "savings_goal",
                "target_value": 5000,
                "category_id": 1,
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        assert progress["current_value"] == 2500
        assert progress["target_value"] == 5000
        assert progress["progress_percentage"] == 50.0
        assert progress["is_achieved"] is False
        assert progress["category_name"] is not None

    def test_progress_multiple_goals(self, client):
        """GET /api/goals/progress returns progress for all active goals."""
        client.post("/api/networth/categories/seed")

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
                "name": "Savings Rate",
                "goal_type": "savings_rate",
                "target_value": 20,
            },
        )
        client.post(
            "/api/goals",
            json={
                "name": "Vacation Fund",
                "goal_type": "savings_goal",
                "target_value": 5000,
                "category_id": 1,
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
            assert "status" in progress
            assert "data_months" in progress

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


class TestGoalStatus:
    """Tests for on-track/behind status calculation."""

    def test_status_no_target_date(self, client):
        """Status is None when no target_date is set."""
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
        assert progress["status"] is None

    def test_status_not_enough_data(self, client):
        """Status is None when less than 3 months of data."""
        client.post("/api/networth/categories/seed")

        # Only 2 snapshots
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2025,
                "entries": [{"category_id": 1, "amount": 50000}],
            },
        )
        client.post(
            "/api/networth",
            json={
                "month": 2,
                "year": 2025,
                "entries": [{"category_id": 1, "amount": 52000}],
            },
        )

        client.post(
            "/api/goals",
            json={
                "name": "100k Goal",
                "goal_type": "net_worth",
                "target_value": 100000,
                "target_date": "2026-12-31T00:00:00+00:00",
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        # Only 2 months of data, need 3+ for status
        assert progress["status"] is None
