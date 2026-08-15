"""Tests for goals API endpoints."""

from datetime import date, timedelta


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

    def test_savings_rate_type_rejected(self, client):
        """POST /api/goals rejects the removed savings_rate type."""
        response = client.post(
            "/api/goals",
            json={
                "name": "Save 20%",
                "goal_type": "savings_rate",
                "target_value": 20,
            },
        )
        assert response.status_code == 400

    def test_negative_current_amount_rejected(self, client):
        """POST /api/goals rejects negative current_amount."""
        response = client.post(
            "/api/goals",
            json={
                "name": "Emergency fund",
                "goal_type": "savings_goal",
                "target_value": 6000,
                "current_amount": -1,
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

    def test_savings_goal_without_category(self, client):
        """POST /api/goals accepts a savings_goal without a category link."""
        response = client.post(
            "/api/goals",
            json={
                "name": "Vacation Fund",
                "goal_type": "savings_goal",
                "target_value": 5000,
                "current_amount": 1500,
            },
        )
        assert response.status_code == 201
        data = response.json
        assert data["category_id"] is None
        assert data["current_amount"] == 1500
        assert data["priority"] == 0

    def test_category_only_for_savings_goal(self, client):
        """POST /api/goals rejects category_id on non-savings_goal types."""
        client.post("/api/networth/categories/seed")
        response = client.post(
            "/api/goals",
            json={
                "name": "Pay off loan",
                "goal_type": "debt_payoff",
                "target_value": 3000,
                "category_id": 1,
            },
        )
        assert response.status_code == 400

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

    def test_create_debt_payoff_goal(self, client):
        """POST /api/goals creates a debt payoff goal."""
        response = client.post(
            "/api/goals",
            json={
                "name": "Pay off car loan",
                "goal_type": "debt_payoff",
                "target_value": 8000,
                "current_amount": 2000,
            },
        )
        assert response.status_code == 201
        data = response.json
        assert data["goal_type"] == "debt_payoff"
        assert data["target_value"] == 8000
        assert data["current_amount"] == 2000
        assert data["category_id"] is None
        assert data["priority"] == 0

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

    def test_progress_manual_savings_goal(self, client):
        """GET /api/goals/progress uses current_amount when no category linked."""
        client.post(
            "/api/goals",
            json={
                "name": "Emergency fund",
                "goal_type": "savings_goal",
                "target_value": 6000,
                "current_amount": 1500,
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        assert progress["current_value"] == 1500
        assert progress["progress_percentage"] == 25.0
        assert progress["is_achieved"] is False

    def test_progress_debt_payoff(self, client):
        """GET /api/goals/progress tracks debt payoff via current_amount."""
        client.post(
            "/api/goals",
            json={
                "name": "Pay off car loan",
                "goal_type": "debt_payoff",
                "target_value": 8000,
                "current_amount": 8000,
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        assert progress["current_value"] == 8000
        assert progress["progress_percentage"] == 100.0
        assert progress["is_achieved"] is True

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
                "name": "Pay off loan",
                "goal_type": "debt_payoff",
                "target_value": 3000,
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


def _add_snapshot(client, month, year, category_id, amount):
    """Helper: create a single-category net worth snapshot."""
    return client.post(
        "/api/networth",
        json={
            "month": month,
            "year": year,
            "entries": [{"category_id": category_id, "amount": amount}],
        },
    )


class TestSavingsGoalPace:
    """Tests for the savings-goal pace / on-track math (issue #57)."""

    def test_flat_balance_is_behind_not_on_track(self, client):
        """A stagnant balance should read as 'behind', not 'on track'.

        Regression for the quirk where current_value / data_months treated a
        long-standing balance as if it had all been saved recently, so a
        category that never grew was reported as on track.
        """
        client.post("/api/networth/categories/seed")

        # Balance sits flat at 4000 for three months — no saving happening.
        _add_snapshot(client, 1, 2026, 1, 4000)
        _add_snapshot(client, 2, 2026, 1, 4000)
        _add_snapshot(client, 3, 2026, 1, 4000)

        client.post(
            "/api/goals",
            json={
                "name": "Vacation Fund",
                "goal_type": "savings_goal",
                "target_value": 5000,
                "category_id": 1,
                "target_date": "2027-01-31T00:00:00+00:00",
            },
        )

        progress = client.get("/api/goals/progress").json[0]
        assert progress["status"] == "behind"
        assert progress["recent_monthly"] == 0.0
        assert progress["status_reason"]

    def test_steady_saving_is_on_track(self, client):
        """Saving faster than required reads as 'on track' with a projection."""
        client.post("/api/networth/categories/seed")

        # +1000/month for three months.
        _add_snapshot(client, 1, 2026, 1, 1000)
        _add_snapshot(client, 2, 2026, 1, 2000)
        _add_snapshot(client, 3, 2026, 1, 3000)

        # Need 2000 more by ~10 months out -> 200/mo required, saving 1000/mo.
        client.post(
            "/api/goals",
            json={
                "name": "Vacation Fund",
                "goal_type": "savings_goal",
                "target_value": 5000,
                "category_id": 1,
                "target_date": "2027-01-31T00:00:00+00:00",
            },
        )

        progress = client.get("/api/goals/progress").json[0]
        assert progress["status"] == "on_track"
        assert progress["recent_monthly"] == 1000.0
        assert progress["required_monthly"] is not None
        assert progress["recent_monthly"] >= progress["required_monthly"]
        # Projection should comfortably clear the target.
        assert progress["projected_value"] >= 5000

    def test_slow_saving_is_behind(self, client):
        """Saving slower than required reads as 'behind'."""
        client.post("/api/networth/categories/seed")

        # +100/month for three months -> far short of what's needed.
        _add_snapshot(client, 1, 2026, 1, 1000)
        _add_snapshot(client, 2, 2026, 1, 1100)
        _add_snapshot(client, 3, 2026, 1, 1200)

        client.post(
            "/api/goals",
            json={
                "name": "Vacation Fund",
                "goal_type": "savings_goal",
                "target_value": 5000,
                "category_id": 1,
                "target_date": "2026-09-30T00:00:00+00:00",
            },
        )

        progress = client.get("/api/goals/progress").json[0]
        assert progress["status"] == "behind"
        assert progress["recent_monthly"] == 100.0
        assert progress["recent_monthly"] < progress["required_monthly"]

    def test_no_target_date_has_reason(self, client):
        """Without a target date, status is None but a reason is given."""
        client.post("/api/networth/categories/seed")
        _add_snapshot(client, 1, 2026, 1, 1000)
        _add_snapshot(client, 2, 2026, 1, 2000)
        _add_snapshot(client, 3, 2026, 1, 3000)

        client.post(
            "/api/goals",
            json={
                "name": "Vacation Fund",
                "goal_type": "savings_goal",
                "target_value": 5000,
                "category_id": 1,
            },
        )

        progress = client.get("/api/goals/progress").json[0]
        assert progress["status"] is None
        assert "target date" in progress["status_reason"].lower()

    def test_achieved_goal_is_on_track(self, client):
        """A goal already at/over target is on track regardless of pace."""
        client.post("/api/networth/categories/seed")
        _add_snapshot(client, 1, 2026, 1, 5000)
        _add_snapshot(client, 2, 2026, 1, 5500)
        _add_snapshot(client, 3, 2026, 1, 6000)

        client.post(
            "/api/goals",
            json={
                "name": "Vacation Fund",
                "goal_type": "savings_goal",
                "target_value": 5000,
                "category_id": 1,
                "target_date": "2027-01-31T00:00:00+00:00",
            },
        )

        progress = client.get("/api/goals/progress").json[0]
        assert progress["is_achieved"] is True
        assert progress["status"] == "on_track"


class TestRoadmap:
    """Tests for the sequential roadmap endpoint."""

    @staticmethod
    def _make_surplus(client, net_income_gross=4000, expense=1000):
        """Create a simple budget: untaxed income minus one expense."""
        client.post(
            "/api/income",
            json={
                "name": "Salary",
                "gross_amount": net_income_gross,
                "is_taxed": False,
            },
        )
        client.post("/api/expenses", json={"name": "Rent", "amount": expense})

    def test_empty_roadmap(self, client):
        """GET /api/goals/roadmap with no goals returns an empty plan."""
        response = client.get("/api/goals/roadmap")
        assert response.status_code == 200
        assert response.json["goals"] == []

    def test_waterfall_projection(self, client):
        """Surplus fills goals sequentially; completion dates accumulate."""
        # Surplus: 4000 - 1000 = 3000/month
        self._make_surplus(client)

        client.post(
            "/api/goals",
            json={
                "name": "Pay off card",
                "goal_type": "debt_payoff",
                "target_value": 3000,
            },
        )
        client.post(
            "/api/goals",
            json={
                "name": "Emergency fund",
                "goal_type": "savings_goal",
                "target_value": 6000,
                "current_amount": 0,
            },
        )

        data = client.get("/api/goals/roadmap").json
        assert data["surplus_monthly"] == 3000.0

        first, second = data["goals"]
        # 3000 remaining at 3000/mo -> about a month; the waterfall then takes
        # roughly two more. Steps land on a payday rollover rather than on an
        # exact month count, so these are ranges.
        assert first["status"] == "active"
        assert 1.0 <= first["months_to_complete"] <= 2.0
        assert second["status"] == "upcoming"
        assert 3.0 <= second["months_to_complete"] <= 4.0
        assert first["projected_completion_date"] is not None
        assert second["projected_completion_date"] > first["projected_completion_date"]

    def test_completed_step_consumes_no_surplus(self, client):
        """A finished step is skipped: the surplus flows to the next one."""
        self._make_surplus(client)

        client.post(
            "/api/goals",
            json={
                "name": "Done already",
                "goal_type": "savings_goal",
                "target_value": 1000,
                "current_amount": 1000,
            },
        )
        client.post(
            "/api/goals",
            json={
                "name": "Next up",
                "goal_type": "savings_goal",
                "target_value": 3000,
            },
        )

        data = client.get("/api/goals/roadmap").json
        first, second = data["goals"]
        assert first["status"] == "completed"
        assert first["months_to_complete"] is None
        assert second["status"] == "active"
        # Gets the whole surplus: about a month, at the next payday that covers it
        assert 1.0 <= second["months_to_complete"] <= 2.0

    def test_no_surplus_gives_no_dates(self, client):
        """With zero/negative surplus, steps get no projected dates."""
        self._make_surplus(client, net_income_gross=1000, expense=1500)

        client.post(
            "/api/goals",
            json={
                "name": "Emergency fund",
                "goal_type": "savings_goal",
                "target_value": 6000,
            },
        )

        data = client.get("/api/goals/roadmap").json
        assert data["surplus_monthly"] == -500.0
        step = data["goals"][0]
        assert step["status"] == "active"
        assert step["months_to_complete"] is None
        assert step["projected_completion_date"] is None

    def test_net_worth_goals_excluded(self, client):
        """net_worth goals don't appear on the roadmap."""
        client.post(
            "/api/goals",
            json={
                "name": "100k club",
                "goal_type": "net_worth",
                "target_value": 100000,
            },
        )
        data = client.get("/api/goals/roadmap").json
        assert data["goals"] == []

    def test_category_linked_progress(self, client):
        """A linked category's snapshot balance drives roadmap progress."""
        client.post("/api/networth/categories/seed")
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2026,
                "entries": [{"category_id": 1, "amount": 2500}],
            },
        )
        client.post(
            "/api/goals",
            json={
                "name": "Emergency fund",
                "goal_type": "savings_goal",
                "target_value": 5000,
                "category_id": 1,
            },
        )

        step = client.get("/api/goals/roadmap").json["goals"][0]
        assert step["current_value"] == 2500.0
        assert step["progress_percentage"] == 50.0

    @staticmethod
    def _goal(client, target=3000):
        client.post(
            "/api/goals",
            json={
                "name": "Emergency fund",
                "goal_type": "savings_goal",
                "target_value": target,
                "current_amount": 0,
            },
        )

    @staticmethod
    def _freeze(monkeypatch, year, month, day):
        """Freeze today so payday-to-payday dates are deterministic.

        Both modules, or the roadmap and the budget endpoint answer for
        different days and comparing their figures compares nothing.
        """
        import datetime

        from app.routes import budget as budget_route
        from app.routes import goals as goals_route

        class _FixedDate(datetime.date):
            @classmethod
            def today(cls):
                return cls(year, month, day)

        for module in (goals_route, budget_route):
            monkeypatch.setattr(module, "date", _FixedDate)

    def _annual_bill_budget(self, client):
        """4 000/mo pay on the 25th, 1 000 rent on the 1st, 6 000 insurance
        falling due 2026-07-01.

        Smoothed, that is a 2 500/mo surplus every month. In actual periods it
        is 3 000 in most of them and -3 000 in the one the insurance lands in.
        """
        client.put("/api/settings", json={"payday_day": 25})
        client.post(
            "/api/income",
            json={
                "name": "Salary",
                "gross_amount": 4000,
                "is_taxed": False,
                "due_day": 25,
            },
        )
        client.post(
            "/api/expenses", json={"name": "Rent", "amount": 1000, "due_day": 1}
        )
        client.post(
            "/api/expenses",
            json={
                "name": "Insurance",
                "amount": 6000,
                "frequency_value": 1,
                "frequency_unit": "years",
                "due_day": 1,
                "start_date": "2026-07-01",
            },
        )

    def test_the_roadmap_is_funded_by_what_the_front_page_shows(
        self, client, monkeypatch
    ):
        """The plan advances by exactly the figure the summary card reports.

        Both come out of the one period calculator. Computed separately they
        drifted apart, most visibly over card payments: the card counted them as
        money leaving and the projection did not.
        """
        self._freeze(monkeypatch, 2026, 6, 10)
        self._annual_bill_budget(client)
        client.post("/api/accounts", json={"name": "Checking", "balance": 2000})
        client.post(
            "/api/accounts",
            json={
                "name": "Visa",
                "balance": -400,
                "is_credit": True,
                "payment_due_day": 5,
            },
        )

        card = client.get("/api/budget/current").json["totals"]["period_next"]

        # The card's own arithmetic, from its own figures
        assert card["net"] == (
            card["money_in"] - card["bills"] - card["savings"] - card["card_payments"]
        )
        # The card payment is in there, not quietly dropped
        assert card["card_payments"] == 400.0
        # ...as is the annual bill that falls due in this period
        assert card["bills"] == 7000.0

        # ...and the roadmap advances by that same amount over that same period
        from app import get_session
        from app.routes.goals import _make_period_flow

        with client.application.app_context():
            flow = _make_period_flow(get_session(), date(2026, 6, 10), 25)
            funding = flow(
                date.fromisoformat(card["start"]), date.fromisoformat(card["end"])
            )

        assert float(funding) == card["net"]

    def test_a_step_completes_when_the_money_actually_lands(self, client, monkeypatch):
        """The next paycheck covers the step, so it completes on that payday.

        At the smoothed 2 500/mo the annual bill drags every month down and this
        goal would have waited until 2026-08-25, even though the June paycheck
        arrives long before the July bill does.
        """
        self._freeze(monkeypatch, 2026, 6, 10)
        self._annual_bill_budget(client)
        self._goal(client, target=3900)

        data = client.get("/api/goals/roadmap").json
        assert data["goals"][0]["projected_completion_date"] == "2026-06-25"

    def test_a_yearly_bill_delays_the_step_it_lands_on(self, client, monkeypatch):
        """The other side of the same coin: a step that isn't reached before the
        bill lands waits for the period to recover, rather than being charged a
        twelfth of it every month."""
        self._freeze(monkeypatch, 2026, 6, 10)
        self._annual_bill_budget(client)
        self._goal(client, target=8000)

        data = client.get("/api/goals/roadmap").json
        # Smoothed, 8 000 at 2 500/mo would land on 2026-09-25
        assert data["goals"][0]["projected_completion_date"] == "2026-10-25"

    def test_projection_starts_from_zero_when_square(self, client):
        """No cash and no one-time items: the plan starts from a clean zero."""
        self._make_surplus(client)  # 3000/mo
        self._goal(client)

        data = client.get("/api/goals/roadmap").json
        assert data["starting_position"] == 0.0
        assert data["shortfall_months"] == 0.0
        assert 1.0 <= data["goals"][0]["months_to_complete"] <= 2.0

    def test_card_debt_delays_the_plan(self, client):
        """A negative net position is earned back before step 1 progresses."""
        self._make_surplus(client)  # 3000/mo
        client.post("/api/accounts", json={"name": "Checking", "balance": 500})
        client.post(
            "/api/accounts",
            json={
                "name": "OP Gold",
                "balance": -3500,
                "is_credit": True,
                "payment_due_day": 20,
            },
        )
        self._goal(client)

        data = client.get("/api/goals/roadmap").json
        # 500 - 3500 = -3000 shortfall: a month of surplus clears it, then
        # about one more funds the goal.
        assert data["starting_position"] == -3000.0
        assert data["shortfall_months"] == 1.0
        assert 2.0 <= data["goals"][0]["months_to_complete"] <= 3.5

    def test_card_debt_counted_once_not_twice(self, client):
        """The card is netted via current_balance, not charged again."""
        self._make_surplus(client)
        client.post("/api/accounts", json={"name": "Checking", "balance": 0})
        client.post(
            "/api/accounts",
            json={
                "name": "OP Gold",
                "balance": -3000,
                "is_credit": True,
                "payment_due_day": 20,
            },
        )
        self._goal(client)

        data = client.get("/api/goals/roadmap").json
        # -3000, not -6000: the balance is a single claim on the surplus
        assert data["starting_position"] == -3000.0

    def test_imminent_one_time_delays_the_plan(self, client):
        """A bill landing before the goal completes pushes it out."""
        self._make_surplus(client)  # 3000/mo
        soon = (date.today() + timedelta(days=3)).isoformat()
        client.post(
            "/api/expenses",
            json={
                "name": "Tax bill",
                "amount": 3000,
                "is_ephemeral": True,
                "start_date": soon,
            },
        )
        self._goal(client)

        data = client.get("/api/goals/roadmap").json
        assert data["surplus_monthly"] == 3000.0  # rate is untouched
        assert data["pending_one_time_net"] == -3000.0
        assert data["starting_position"] == -3000.0
        # The bill lands first, so the goal needs a second month of surplus
        assert data["goals"][0]["months_to_complete"] > 1.5

    def test_distant_one_time_does_not_delay_an_earlier_step(self, client):
        """A bill years out doesn't hold up a goal that finishes next month."""
        self._make_surplus(client)  # 3000/mo
        client.post(
            "/api/expenses",
            json={
                "name": "Someday bill",
                "amount": 3000,
                "is_ephemeral": True,
                "start_date": "2099-01-01",
            },
        )
        self._goal(client)  # 3000 target, one month of surplus

        data = client.get("/api/goals/roadmap").json
        # Still counted as a pending claim...
        assert data["pending_one_time_net"] == -3000.0
        # ...but it lands in 2099, long after this step completes
        assert data["goals"][0]["months_to_complete"] <= 2.0

    def test_past_one_time_is_settled(self, client):
        """A one-time item dated in the past no longer claims the surplus."""
        self._make_surplus(client)
        client.post(
            "/api/expenses",
            json={
                "name": "Old bill",
                "amount": 3000,
                "is_ephemeral": True,
                "start_date": "2000-01-01",
            },
        )
        self._goal(client)

        data = client.get("/api/goals/roadmap").json
        assert data["pending_one_time_net"] == 0.0
        assert data["starting_position"] == 0.0

    def test_spare_cash_is_not_a_head_start(self, client):
        """Cash outside the tracked account never pulls a goal forward."""
        self._make_surplus(client)  # 3000/mo
        client.post("/api/accounts", json={"name": "Checking", "balance": 50000})
        self._goal(client)

        data = client.get("/api/goals/roadmap").json
        assert data["starting_position"] == 0.0
        # Still a full month of surplus, not "already done"
        assert 1.0 <= data["goals"][0]["months_to_complete"] <= 2.0

    def test_cash_covers_a_pending_one_time_bill(self, client):
        """A one-off bill the balance plainly covers is not a shortfall.

        Spare cash still isn't a head start, so the plan starts from zero rather
        than from the balance — but it does mean the user isn't behind.
        """
        self._make_surplus(client)
        client.post("/api/accounts", json={"name": "Checking", "balance": 10000})
        client.post(
            "/api/expenses",
            json={
                "name": "Vacation",
                "amount": 800,
                "is_ephemeral": True,
                "start_date": "2099-01-01",
            },
        )
        self._goal(client)

        data = client.get("/api/goals/roadmap").json
        assert data["pending_one_time_net"] == -800.0
        assert data["starting_position"] == 0.0
        assert data["shortfall_months"] == 0.0

    def test_one_time_bill_beyond_the_balance_is_a_shortfall(self, client):
        """Only the part the balance can't cover counts as starting behind."""
        self._make_surplus(client)  # 3000/mo
        client.post("/api/accounts", json={"name": "Checking", "balance": 500})
        client.post(
            "/api/expenses",
            json={
                "name": "Tax bill",
                "amount": 3500,
                "is_ephemeral": True,
                "start_date": "2099-01-01",
            },
        )
        self._goal(client)

        data = client.get("/api/goals/roadmap").json
        assert data["starting_position"] == -3000.0
        assert data["shortfall_months"] == 1.0

    def test_pending_one_time_income_offsets_a_bill(self, client):
        """A pending bonus nets against a pending bill rather than being lost."""
        self._make_surplus(client)
        client.post(
            "/api/expenses",
            json={
                "name": "Tax bill",
                "amount": 3000,
                "is_ephemeral": True,
                "start_date": "2099-01-01",
            },
        )
        client.post(
            "/api/income",
            json={
                "name": "Bonus",
                "gross_amount": 2000,
                "is_taxed": False,
                "is_ephemeral": True,
                "start_date": "2099-01-01",
            },
        )
        self._goal(client)

        data = client.get("/api/goals/roadmap").json
        assert data["pending_one_time_net"] == -1000.0
        assert data["starting_position"] == -1000.0

    def test_no_projection_without_surplus_despite_shortfall(self, client):
        """A shortfall with no surplus still yields no completion date."""
        self._make_surplus(client, net_income_gross=1000, expense=1000)
        client.post(
            "/api/accounts",
            json={"name": "OP Gold", "balance": -500, "is_credit": True},
        )
        self._goal(client)

        data = client.get("/api/goals/roadmap").json
        assert data["surplus_monthly"] == 0.0
        assert data["shortfall_months"] == 0.0
        assert data["goals"][0]["projected_completion_date"] is None

    def test_completion_lands_on_a_payday(self, client):
        """The budget month rolls over on payday, so steps complete there."""
        client.put("/api/settings", json={"payday_day": 15})
        self._make_surplus(client)  # 3000/mo
        self._goal(client, target=9000)

        done = client.get("/api/goals/roadmap").json["goals"][0]
        completion = date.fromisoformat(done["projected_completion_date"])
        assert completion.day == 15

    def test_payday_day_shifts_the_completion_date(self, client):
        """A different rollover day moves the projection to that day."""
        self._make_surplus(client)
        self._goal(client, target=9000)

        client.put("/api/settings", json={"payday_day": 5})
        fifth = client.get("/api/goals/roadmap").json["goals"][0]

        client.put("/api/settings", json={"payday_day": 25})
        twenty_fifth = client.get("/api/goals/roadmap").json["goals"][0]

        assert date.fromisoformat(fifth["projected_completion_date"]).day == 5
        assert date.fromisoformat(twenty_fifth["projected_completion_date"]).day == 25
        assert (
            fifth["projected_completion_date"]
            != twenty_fifth["projected_completion_date"]
        )

    def test_part_period_is_not_credited_a_full_month(self, client):
        """The stub before the next payday accrues pro rata, not in full."""
        # Roll over tomorrow: today's stub is worth ~1 day of surplus, so a
        # one-month goal cannot complete at that first payday.
        tomorrow = date.today() + timedelta(days=1)
        client.put("/api/settings", json={"payday_day": tomorrow.day})
        self._make_surplus(client)  # 3000/mo
        self._goal(client, target=3000)

        done = client.get("/api/goals/roadmap").json["goals"][0]
        completion = date.fromisoformat(done["projected_completion_date"])
        assert completion > tomorrow


class TestReorder:
    """Tests for PUT /api/goals/reorder."""

    @staticmethod
    def _create_step(client, name, target=1000):
        response = client.post(
            "/api/goals",
            json={
                "name": name,
                "goal_type": "savings_goal",
                "target_value": target,
            },
        )
        return response.json["id"]

    def test_reorder_goals(self, client):
        """Reordering updates priorities and the roadmap order."""
        first = self._create_step(client, "First")
        second = self._create_step(client, "Second")
        third = self._create_step(client, "Third")

        response = client.put(
            "/api/goals/reorder", json={"goal_ids": [third, first, second]}
        )
        assert response.status_code == 200
        assert [g["priority"] for g in response.json] == [0, 1, 2]

        names = [
            step["goal"]["name"]
            for step in client.get("/api/goals/roadmap").json["goals"]
        ]
        assert names == ["Third", "First", "Second"]

    def test_reorder_missing_goal(self, client):
        """Unknown ids return 404."""
        goal_id = self._create_step(client, "Only")
        response = client.put("/api/goals/reorder", json={"goal_ids": [goal_id, 99999]})
        assert response.status_code == 404

    def test_reorder_rejects_non_roadmap_goal(self, client):
        """net_worth goals can't be part of the roadmap order."""
        nw = client.post(
            "/api/goals",
            json={
                "name": "100k",
                "goal_type": "net_worth",
                "target_value": 100000,
            },
        ).json["id"]
        response = client.put("/api/goals/reorder", json={"goal_ids": [nw]})
        assert response.status_code == 400

    def test_reorder_requires_list(self, client):
        """Missing/invalid goal_ids returns 400."""
        response = client.put("/api/goals/reorder", json={"goal_ids": "nope"})
        assert response.status_code == 400

    def test_new_goals_append_to_end(self, client):
        """Each new roadmap goal gets the next priority."""
        self._create_step(client, "A")
        self._create_step(client, "B")
        goals = client.get("/api/goals").json
        priorities = {g["name"]: g["priority"] for g in goals}
        assert priorities == {"A": 0, "B": 1}

    def test_surplus_normalizes_frequencies(self, client):
        """The roadmap surplus uses monthly-normalized income and expenses."""
        client.post(
            "/api/income",
            json={"name": "Salary", "gross_amount": 4000, "is_taxed": False},
        )
        client.post(
            "/api/expenses",
            json={
                "name": "Water",
                "amount": 300,
                "frequency_value": 3,
                "frequency_unit": "months",
            },
        )
        client.post(
            "/api/expenses",
            json={
                "name": "One-off",
                "amount": 5000,
                "is_ephemeral": True,
                "start_date": "2099-01-01",
            },
        )

        data = client.get("/api/goals/roadmap").json
        # 4000 - 300/3; the ephemeral one-off doesn't drag the rate down
        assert data["surplus_monthly"] == 3900.0
