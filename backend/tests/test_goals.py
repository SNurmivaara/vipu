"""Tests for goals API endpoints."""


class TestGoalValidation:
    """Tests for goal input validation."""

    def test_goal_missing_name(self, client):
        """POST /api/goals requires name."""
        response = client.post(
            "/api/goals",
            json={"goal_type": "net_worth_target", "target_value": 100000},
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
            json={"name": "Test Goal", "goal_type": "net_worth_target"},
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
                "goal_type": "net_worth_target",
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
                "goal_type": "net_worth_target",
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
                "goal_type": "net_worth_target",
                "target_value": 1_000_000_001,
            },
        )
        assert response.status_code == 400

    def test_goal_category_rate_exceeds_100(self, client):
        """POST /api/goals rejects category_rate > 100%."""
        # First seed categories to get a valid category_id
        client.post("/api/networth/categories/seed")

        response = client.post(
            "/api/goals",
            json={
                "name": "Save Too Much",
                "goal_type": "category_rate",
                "target_value": 101,
                "category_id": 1,
                "tracking_period": "month",
            },
        )
        assert response.status_code == 400

    def test_goal_category_rate_negative(self, client):
        """POST /api/goals rejects negative category_rate."""
        client.post("/api/networth/categories/seed")

        response = client.post(
            "/api/goals",
            json={
                "name": "Negative Rate",
                "goal_type": "category_rate",
                "target_value": -10,
                "category_id": 1,
                "tracking_period": "month",
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
                "goal_type": "net_worth_target",
                "target_value": 100000,
                "target_date": "not-a-date",
            },
        )
        assert response.status_code == 400

    def test_category_goal_requires_category_id(self, client):
        """POST /api/goals with category_target requires category_id."""
        response = client.post(
            "/api/goals",
            json={
                "name": "Category Target",
                "goal_type": "category_target",
                "target_value": 50000,
            },
        )
        assert response.status_code == 400
        assert "category_id" in response.json["error"].lower()

    def test_category_monthly_requires_category_id(self, client):
        """POST /api/goals with category_monthly requires category_id."""
        response = client.post(
            "/api/goals",
            json={
                "name": "Monthly Savings",
                "goal_type": "category_monthly",
                "target_value": 500,
                "tracking_period": "month",
            },
        )
        assert response.status_code == 400
        assert "category_id" in response.json["error"].lower()

    def test_category_rate_requires_category_id(self, client):
        """POST /api/goals with category_rate requires category_id."""
        response = client.post(
            "/api/goals",
            json={
                "name": "Savings Rate",
                "goal_type": "category_rate",
                "target_value": 30,
                "tracking_period": "month",
            },
        )
        assert response.status_code == 400
        assert "category_id" in response.json["error"].lower()

    def test_category_monthly_requires_tracking_period(self, client):
        """POST /api/goals with category_monthly requires tracking_period."""
        client.post("/api/networth/categories/seed")

        response = client.post(
            "/api/goals",
            json={
                "name": "Monthly Savings",
                "goal_type": "category_monthly",
                "target_value": 500,
                "category_id": 1,
            },
        )
        assert response.status_code == 400
        assert "tracking_period" in response.json["error"].lower()

    def test_category_rate_requires_tracking_period(self, client):
        """POST /api/goals with category_rate requires tracking_period."""
        client.post("/api/networth/categories/seed")

        response = client.post(
            "/api/goals",
            json={
                "name": "Savings Rate",
                "goal_type": "category_rate",
                "target_value": 30,
                "category_id": 1,
            },
        )
        assert response.status_code == 400
        assert "tracking_period" in response.json["error"].lower()

    def test_invalid_tracking_period(self, client):
        """POST /api/goals rejects invalid tracking_period."""
        client.post("/api/networth/categories/seed")

        response = client.post(
            "/api/goals",
            json={
                "name": "Invalid Period",
                "goal_type": "category_monthly",
                "target_value": 500,
                "category_id": 1,
                "tracking_period": "weekly",
            },
        )
        assert response.status_code == 400
        assert "tracking_period" in response.json["error"].lower()

    def test_nonexistent_category(self, client):
        """POST /api/goals with nonexistent category_id returns 404."""
        response = client.post(
            "/api/goals",
            json={
                "name": "Bad Category",
                "goal_type": "category_target",
                "target_value": 50000,
                "category_id": 99999,
            },
        )
        assert response.status_code == 404


class TestGoalCRUD:
    """Tests for goal CRUD operations."""

    def test_create_net_worth_target_goal(self, client):
        """POST /api/goals creates a net worth target goal."""
        response = client.post(
            "/api/goals",
            json={
                "name": "100k Net Worth",
                "goal_type": "net_worth_target",
                "target_value": 100000,
            },
        )
        assert response.status_code == 201
        data = response.json
        assert data["name"] == "100k Net Worth"
        assert data["goal_type"] == "net_worth_target"
        assert data["target_value"] == 100000
        assert data["is_active"] is True
        assert data["target_date"] is None
        assert data["category_id"] is None
        assert data["tracking_period"] is None
        assert "id" in data
        assert "created_at" in data

    def test_create_category_target_goal(self, client):
        """POST /api/goals creates a category target goal."""
        client.post("/api/networth/categories/seed")

        response = client.post(
            "/api/goals",
            json={
                "name": "50k Emergency Fund",
                "goal_type": "category_target",
                "target_value": 50000,
                "category_id": 1,
            },
        )
        assert response.status_code == 201
        data = response.json
        assert data["goal_type"] == "category_target"
        assert data["target_value"] == 50000
        assert data["category_id"] == 1

    def test_create_category_monthly_goal(self, client):
        """POST /api/goals creates a category monthly goal."""
        client.post("/api/networth/categories/seed")

        response = client.post(
            "/api/goals",
            json={
                "name": "Save 500€/month",
                "goal_type": "category_monthly",
                "target_value": 500,
                "category_id": 1,
                "tracking_period": "quarter",
            },
        )
        assert response.status_code == 201
        data = response.json
        assert data["goal_type"] == "category_monthly"
        assert data["target_value"] == 500
        assert data["category_id"] == 1
        assert data["tracking_period"] == "quarter"

    def test_create_category_rate_goal(self, client):
        """POST /api/goals creates a category rate goal."""
        client.post("/api/networth/categories/seed")

        response = client.post(
            "/api/goals",
            json={
                "name": "30% Savings Rate",
                "goal_type": "category_rate",
                "target_value": 30,
                "category_id": 1,
                "tracking_period": "year",
            },
        )
        assert response.status_code == 201
        data = response.json
        assert data["goal_type"] == "category_rate"
        assert data["target_value"] == 30
        assert data["tracking_period"] == "year"

    def test_create_goal_with_target_date(self, client):
        """POST /api/goals with target_date."""
        response = client.post(
            "/api/goals",
            json={
                "name": "Goal with Date",
                "goal_type": "net_worth_target",
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
                "goal_type": "net_worth_target",
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
                "goal_type": "net_worth_target",
                "target_value": 10000,
            },
        )
        client.post(
            "/api/goals",
            json={
                "name": "Goal 2",
                "goal_type": "category_target",
                "target_value": 25000,
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
                "goal_type": "net_worth_target",
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
                "goal_type": "net_worth_target",
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
                "goal_type": "net_worth_target",
                "target_value": 50000,
            },
        )
        goal_id = create_response.json["id"]

        response = client.put(f"/api/goals/{goal_id}", json={"target_value": 75000})
        assert response.status_code == 200
        assert response.json["target_value"] == 75000

    def test_update_goal_type(self, client):
        """PUT /api/goals/<id> updates goal_type."""
        client.post("/api/networth/categories/seed")

        create_response = client.post(
            "/api/goals",
            json={
                "name": "Test Goal",
                "goal_type": "net_worth_target",
                "target_value": 50000,
            },
        )
        goal_id = create_response.json["id"]

        response = client.put(
            f"/api/goals/{goal_id}",
            json={"goal_type": "category_target", "category_id": 1},
        )
        assert response.status_code == 200
        assert response.json["goal_type"] == "category_target"

    def test_update_goal_add_target_date(self, client):
        """PUT /api/goals/<id> adds target_date."""
        create_response = client.post(
            "/api/goals",
            json={
                "name": "Test Goal",
                "goal_type": "net_worth_target",
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
                "goal_type": "net_worth_target",
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
                "goal_type": "net_worth_target",
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
                "name": "Category Goal",
                "goal_type": "category_target",
                "target_value": 50000,
                "category_id": 1,
            },
        )
        goal_id = create_response.json["id"]

        response = client.put(f"/api/goals/{goal_id}", json={"category_id": 2})
        assert response.status_code == 200
        assert response.json["category_id"] == 2

    def test_update_goal_tracking_period(self, client):
        """PUT /api/goals/<id> updates tracking_period."""
        client.post("/api/networth/categories/seed")

        create_response = client.post(
            "/api/goals",
            json={
                "name": "Monthly Goal",
                "goal_type": "category_monthly",
                "target_value": 500,
                "category_id": 1,
                "tracking_period": "month",
            },
        )
        goal_id = create_response.json["id"]

        response = client.put(
            f"/api/goals/{goal_id}", json={"tracking_period": "quarter"}
        )
        assert response.status_code == 200
        assert response.json["tracking_period"] == "quarter"

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
                "goal_type": "net_worth_target",
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
                "goal_type": "net_worth_target",
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
                "goal_type": "net_worth_target",
                "target_value": 100000,
                "is_active": False,
            },
        )

        response = client.get("/api/goals/progress")
        assert response.status_code == 200
        assert response.json == []

    def test_progress_net_worth_target_no_snapshot(self, client):
        """GET /api/goals/progress with net_worth_target but no snapshots."""
        client.post(
            "/api/goals",
            json={
                "name": "100k Goal",
                "goal_type": "net_worth_target",
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

    def test_progress_net_worth_target_with_snapshot(self, client):
        """GET /api/goals/progress with net_worth_target and snapshot data."""
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
                "goal_type": "net_worth_target",
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

    def test_progress_net_worth_target_achieved(self, client):
        """GET /api/goals/progress when net_worth_target is achieved."""
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
                "goal_type": "net_worth_target",
                "target_value": 100000,
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        assert progress["current_value"] == 120000
        # Progress capped at 100%
        assert progress["progress_percentage"] == 100.0
        assert progress["is_achieved"] is True

    def test_progress_category_target_no_snapshot(self, client):
        """GET /api/goals/progress with category_target but no snapshots."""
        client.post("/api/networth/categories/seed")

        client.post(
            "/api/goals",
            json={
                "name": "50k Emergency Fund",
                "goal_type": "category_target",
                "target_value": 50000,
                "category_id": 1,
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        assert progress["current_value"] == 0
        assert progress["target_value"] == 50000
        assert progress["progress_percentage"] == 0
        assert progress["is_achieved"] is False

    def test_progress_category_target_with_snapshot(self, client):
        """GET /api/goals/progress with category_target and snapshot."""
        client.post("/api/networth/categories/seed")

        # Create snapshot with category 1 having 25000
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2025,
                "entries": [
                    {"category_id": 1, "amount": 25000},
                ],
            },
        )

        client.post(
            "/api/goals",
            json={
                "name": "50k Emergency Fund",
                "goal_type": "category_target",
                "target_value": 50000,
                "category_id": 1,
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        assert progress["current_value"] == 25000
        assert progress["target_value"] == 50000
        assert progress["progress_percentage"] == 50.0
        assert progress["is_achieved"] is False
        assert progress["details"]["category_name"] is not None

    def test_progress_category_monthly_no_snapshots(self, client):
        """GET /api/goals/progress with category_monthly but no snapshots."""
        client.post("/api/networth/categories/seed")

        client.post(
            "/api/goals",
            json={
                "name": "Save 500/month",
                "goal_type": "category_monthly",
                "target_value": 500,
                "category_id": 1,
                "tracking_period": "month",
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        assert progress["current_value"] == 0
        assert progress["progress_percentage"] == 0
        assert progress["is_achieved"] is False

    def test_progress_category_monthly_with_change(self, client):
        """GET /api/goals/progress tracks monthly change in category."""
        client.post("/api/networth/categories/seed")

        # Create two snapshots to calculate change
        # Older snapshot
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2025,
                "entries": [{"category_id": 1, "amount": 10000}],
            },
        )

        # Newer snapshot with 600 increase
        client.post(
            "/api/networth",
            json={
                "month": 2,
                "year": 2025,
                "entries": [{"category_id": 1, "amount": 10600}],
            },
        )

        client.post(
            "/api/goals",
            json={
                "name": "Save 500/month",
                "goal_type": "category_monthly",
                "target_value": 500,
                "category_id": 1,
                "tracking_period": "month",
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        # Change from 10000 to 10600 = 600, which exceeds target of 500
        assert progress["current_value"] == 600
        assert progress["target_value"] == 500
        assert progress["progress_percentage"] == 100.0
        assert progress["is_achieved"] is True
        assert progress["details"]["tracking_period"] == "month"
        assert progress["details"]["months_tracked"] == 1

    def test_progress_category_monthly_quarter_average(self, client):
        """GET /api/goals/progress averages monthly changes over quarter."""
        client.post("/api/networth/categories/seed")

        # Create 4 snapshots for a quarter
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
                "entries": [{"category_id": 1, "amount": 10600}],  # +600
            },
        )
        client.post(
            "/api/networth",
            json={
                "month": 3,
                "year": 2025,
                "entries": [{"category_id": 1, "amount": 11000}],  # +400
            },
        )
        client.post(
            "/api/networth",
            json={
                "month": 4,
                "year": 2025,
                "entries": [{"category_id": 1, "amount": 11500}],  # +500
            },
        )

        client.post(
            "/api/goals",
            json={
                "name": "Save 500/month",
                "goal_type": "category_monthly",
                "target_value": 500,
                "category_id": 1,
                "tracking_period": "quarter",
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        # Average: (500 + 400 + 600) / 3 = 500
        assert progress["current_value"] == 500
        assert progress["target_value"] == 500
        assert progress["is_achieved"] is True
        assert progress["details"]["months_tracked"] == 3

    def test_progress_category_rate_no_income(self, client):
        """GET /api/goals/progress with category_rate but no income."""
        client.post("/api/networth/categories/seed")

        client.post(
            "/api/goals",
            json={
                "name": "30% Savings Rate",
                "goal_type": "category_rate",
                "target_value": 30,
                "category_id": 1,
                "tracking_period": "month",
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        # No income means 0 rate
        assert progress["current_value"] == 0
        assert progress["progress_percentage"] == 0
        assert progress["is_achieved"] is False

    def test_progress_category_rate_with_income(self, client):
        """GET /api/goals/progress calculates rate as % of income."""
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
                "name": "30% Savings Rate",
                "goal_type": "category_rate",
                "target_value": 30,
                "category_id": 1,
                "tracking_period": "month",
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        # 1000 / 3750 * 100 = 26.67%
        # progress = 26.67 / 30 * 100 = 88.89%
        assert 25 < progress["current_value"] < 28  # ~26.67%
        assert progress["target_value"] == 30
        assert progress["is_achieved"] is False
        assert "net_income" in progress["details"]
        assert progress["details"]["net_income"] == 3750

    def test_progress_category_rate_achieved(self, client):
        """GET /api/goals/progress when category_rate is achieved."""
        client.post("/api/networth/categories/seed")

        # Create income: 5000 gross, 25% tax = 3750 net
        client.post(
            "/api/income",
            json={"name": "Salary", "gross_amount": 5000, "is_taxed": True},
        )

        # Create snapshots showing 1500/month savings
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
                "entries": [{"category_id": 1, "amount": 11500}],  # +1500
            },
        )

        client.post(
            "/api/goals",
            json={
                "name": "30% Savings Rate",
                "goal_type": "category_rate",
                "target_value": 30,
                "category_id": 1,
                "tracking_period": "month",
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        # 1500 / 3750 * 100 = 40%
        assert progress["current_value"] == 40
        assert progress["is_achieved"] is True

    def test_progress_multiple_goals(self, client):
        """GET /api/goals/progress returns progress for all active goals."""
        client.post("/api/networth/categories/seed")

        client.post(
            "/api/goals",
            json={
                "name": "Net Worth Goal",
                "goal_type": "net_worth_target",
                "target_value": 100000,
            },
        )
        client.post(
            "/api/goals",
            json={
                "name": "Category Target",
                "goal_type": "category_target",
                "target_value": 50000,
                "category_id": 1,
            },
        )
        client.post(
            "/api/goals",
            json={
                "name": "Monthly Savings",
                "goal_type": "category_monthly",
                "target_value": 500,
                "category_id": 1,
                "tracking_period": "month",
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
                "goal_type": "net_worth_target",
                "target_value": 100000,
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        # Should use June 2024 (50000), not January (30000)
        assert progress["current_value"] == 50000
        assert progress["details"]["latest_month"] == "2024-06"

    def test_progress_liability_category_target(self, client):
        """GET /api/goals/progress handles liability target correctly."""
        client.post("/api/networth/categories/seed")

        # Create snapshot with liability (category 11 = loans, negative value)
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2025,
                "entries": [{"category_id": 11, "amount": -15000}],
            },
        )

        # Goal: Pay down loan to 10000
        client.post(
            "/api/goals",
            json={
                "name": "Pay Down Loan",
                "goal_type": "category_target",
                "target_value": 10000,
                "category_id": 11,
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        # For liability, we show absolute value
        assert progress["current_value"] == 15000
        assert progress["target_value"] == 10000

    def test_progress_liability_monthly_paydown(self, client):
        """GET /api/goals/progress tracks liability paydown correctly."""
        client.post("/api/networth/categories/seed")

        # Create snapshots showing loan paydown
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2025,
                "entries": [{"category_id": 11, "amount": -20000}],
            },
        )
        client.post(
            "/api/networth",
            json={
                "month": 2,
                "year": 2025,
                "entries": [{"category_id": 11, "amount": -19500}],  # Paid 500
            },
        )

        # Goal: Pay 500/month toward loan
        client.post(
            "/api/goals",
            json={
                "name": "Pay 500/month",
                "goal_type": "category_monthly",
                "target_value": 500,
                "category_id": 11,
                "tracking_period": "month",
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]
        # For liability, decrease = positive progress
        # -19500 - (-20000) = 500, flipped sign = 500
        assert progress["current_value"] == 500
        assert progress["is_achieved"] is True

    def test_valid_tracking_periods(self, client):
        """POST /api/goals accepts all valid tracking periods."""
        client.post("/api/networth/categories/seed")

        valid_periods = ["month", "quarter", "half_year", "year"]

        for period in valid_periods:
            response = client.post(
                "/api/goals",
                json={
                    "name": f"Goal with {period}",
                    "goal_type": "category_monthly",
                    "target_value": 500,
                    "category_id": 1,
                    "tracking_period": period,
                },
            )
            assert response.status_code == 201, f"Failed for period: {period}"
            assert response.json["tracking_period"] == period


class TestGoalForecast:
    """Tests for goal forecast calculations."""

    def test_progress_includes_forecast_for_net_worth_target(self, client):
        """GET /api/goals/progress includes forecast for net_worth_target goals."""
        client.post("/api/networth/categories/seed")

        # Create snapshots showing growth
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2025,
                "entries": [{"category_id": 1, "amount": 40000}],
            },
        )
        client.post(
            "/api/networth",
            json={
                "month": 2,
                "year": 2025,
                "entries": [{"category_id": 1, "amount": 42000}],  # +2000/month
            },
        )
        client.post(
            "/api/networth",
            json={
                "month": 3,
                "year": 2025,
                "entries": [{"category_id": 1, "amount": 44000}],  # +2000/month
            },
        )
        client.post(
            "/api/networth",
            json={
                "month": 4,
                "year": 2025,
                "entries": [{"category_id": 1, "amount": 46000}],  # +2000/month
            },
        )

        # Goal: reach 100k
        client.post(
            "/api/goals",
            json={
                "name": "100k Goal",
                "goal_type": "net_worth_target",
                "target_value": 100000,
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]

        assert "forecast" in progress
        assert progress["forecast"] is not None
        assert "forecast_date" in progress["forecast"]
        assert "months_until_target" in progress["forecast"]
        assert "on_track" in progress["forecast"]
        assert "required_monthly_change" in progress["forecast"]
        assert "current_monthly_change" in progress["forecast"]

        # 46000 current, need 54000 more, at 2000/month = 27 months
        assert progress["forecast"]["months_until_target"] == 28
        assert progress["forecast"]["current_monthly_change"] == 2000

    def test_progress_forecast_with_target_date_on_track(self, client):
        """GET /api/goals/progress shows on_track=True when meeting deadline."""
        client.post("/api/networth/categories/seed")

        # Create snapshots showing 2000/month growth
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2025,
                "entries": [{"category_id": 1, "amount": 90000}],
            },
        )
        client.post(
            "/api/networth",
            json={
                "month": 2,
                "year": 2025,
                "entries": [{"category_id": 1, "amount": 92000}],
            },
        )
        client.post(
            "/api/networth",
            json={
                "month": 3,
                "year": 2025,
                "entries": [{"category_id": 1, "amount": 94000}],
            },
        )
        client.post(
            "/api/networth",
            json={
                "month": 4,
                "year": 2025,
                "entries": [{"category_id": 1, "amount": 96000}],
            },
        )

        # Goal: reach 100k by end of year (8 months away)
        # Need 4000 more, at 2000/month = 2 months needed
        client.post(
            "/api/goals",
            json={
                "name": "100k by EOY",
                "goal_type": "net_worth_target",
                "target_value": 100000,
                "target_date": "2025-12-31T00:00:00+00:00",
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]

        assert progress["forecast"]["on_track"] is True
        # 8 months to go, need 4000, so 500/month required
        # Currently saving 2000/month, so on track
        assert progress["forecast"]["current_monthly_change"] == 2000

    def test_progress_forecast_with_target_date_behind(self, client):
        """GET /api/goals/progress shows on_track=False when behind schedule."""
        client.post("/api/networth/categories/seed")

        # Create snapshots showing slow growth
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
                "entries": [{"category_id": 1, "amount": 51000}],  # +1000/month
            },
        )
        client.post(
            "/api/networth",
            json={
                "month": 3,
                "year": 2025,
                "entries": [{"category_id": 1, "amount": 52000}],
            },
        )
        client.post(
            "/api/networth",
            json={
                "month": 4,
                "year": 2025,
                "entries": [{"category_id": 1, "amount": 53000}],
            },
        )

        # Goal: reach 100k by June 2025 (2 months away)
        # Need 47000 more, in 2 months = 23500/month required
        # Currently at 1000/month = way behind
        client.post(
            "/api/goals",
            json={
                "name": "100k by June",
                "goal_type": "net_worth_target",
                "target_value": 100000,
                "target_date": "2025-06-30T00:00:00+00:00",
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]

        assert progress["forecast"]["on_track"] is False
        assert progress["forecast"]["required_monthly_change"] == 23500

    def test_progress_forecast_no_target_date(self, client):
        """Forecast without target_date shows on_track based on growth."""
        client.post("/api/networth/categories/seed")

        # Create snapshots showing growth
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
                "goal_type": "net_worth_target",
                "target_value": 100000,
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]

        # No target date, but making progress = on track
        assert progress["forecast"]["on_track"] is True
        assert progress["forecast"]["required_monthly_change"] == 0

    def test_progress_forecast_no_growth(self, client):
        """GET /api/goals/progress forecast with no growth shows null forecast_date."""
        client.post("/api/networth/categories/seed")

        # Create snapshots with no change
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
                "entries": [{"category_id": 1, "amount": 50000}],  # No change
            },
        )

        client.post(
            "/api/goals",
            json={
                "name": "100k Goal",
                "goal_type": "net_worth_target",
                "target_value": 100000,
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]

        assert progress["forecast"]["forecast_date"] is None
        assert progress["forecast"]["months_until_target"] is None
        assert progress["forecast"]["current_monthly_change"] == 0

    def test_progress_forecast_category_target(self, client):
        """GET /api/goals/progress includes forecast for category_target goals."""
        client.post("/api/networth/categories/seed")

        # Create snapshots for category growth
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
                "entries": [{"category_id": 1, "amount": 12000}],
            },
        )
        client.post(
            "/api/networth",
            json={
                "month": 3,
                "year": 2025,
                "entries": [{"category_id": 1, "amount": 14000}],
            },
        )
        client.post(
            "/api/networth",
            json={
                "month": 4,
                "year": 2025,
                "entries": [{"category_id": 1, "amount": 16000}],  # +2000/month
            },
        )

        client.post(
            "/api/goals",
            json={
                "name": "50k in Savings",
                "goal_type": "category_target",
                "target_value": 50000,
                "category_id": 1,
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]

        assert progress["forecast"] is not None
        # 16000 current, need 34000 more, at 2000/month = 17 months
        assert progress["forecast"]["months_until_target"] == 18
        assert progress["forecast"]["current_monthly_change"] == 2000

    def test_progress_no_forecast_for_monthly_goals(self, client):
        """GET /api/goals/progress returns null forecast for category_monthly."""
        client.post("/api/networth/categories/seed")

        client.post(
            "/api/goals",
            json={
                "name": "Monthly Savings",
                "goal_type": "category_monthly",
                "target_value": 500,
                "category_id": 1,
                "tracking_period": "month",
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]

        # Monthly goals don't have forecast info
        assert progress["forecast"] is None

    def test_progress_forecast_goal_already_achieved(self, client):
        """GET /api/goals/progress forecast shows achieved goal correctly."""
        client.post("/api/networth/categories/seed")

        # Create snapshot with goal already met
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2025,
                "entries": [{"category_id": 1, "amount": 120000}],
            },
        )

        client.post(
            "/api/goals",
            json={
                "name": "100k Goal",
                "goal_type": "net_worth_target",
                "target_value": 100000,
            },
        )

        response = client.get("/api/goals/progress")
        progress = response.json[0]

        assert progress["is_achieved"] is True
        assert progress["forecast"]["months_until_target"] == 0
        assert progress["forecast"]["on_track"] is True
