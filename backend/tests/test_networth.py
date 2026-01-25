"""Tests for net worth API endpoints."""

import pytest

# =============================================================================
# Category Tests
# =============================================================================


class TestCategoryList:
    """Tests for listing categories."""

    def test_list_categories_empty(self, client):
        """GET /api/networth/categories returns empty list initially."""
        response = client.get("/api/networth/categories")
        assert response.status_code == 200
        assert response.json == []

    def test_list_categories_sorted(self, client):
        """GET /api/networth/categories returns categories sorted by display_order."""
        client.post(
            "/api/networth/categories",
            json={
                "name": "Second",
                "category_type": "asset",
                "category_group": "cash",
                "display_order": 2,
            },
        )
        client.post(
            "/api/networth/categories",
            json={
                "name": "First",
                "category_type": "asset",
                "category_group": "cash",
                "display_order": 1,
            },
        )

        response = client.get("/api/networth/categories")
        assert response.status_code == 200
        assert len(response.json) == 2
        assert response.json[0]["name"] == "First"
        assert response.json[1]["name"] == "Second"


class TestCategoryCreate:
    """Tests for creating categories."""

    def test_create_category_minimal(self, client):
        """POST /api/networth/categories creates category with required fields."""
        response = client.post(
            "/api/networth/categories",
            json={
                "name": "My Savings",
                "category_type": "asset",
                "category_group": "cash",
            },
        )
        assert response.status_code == 201
        data = response.json

        assert data["name"] == "My Savings"
        assert data["category_type"] == "asset"
        assert data["category_group"] == "cash"
        assert data["is_personal"] is True  # Default
        assert data["display_order"] == 0  # Default
        assert "id" in data
        assert "created_at" in data

    def test_create_category_full(self, client):
        """POST /api/networth/categories creates category with all fields."""
        response = client.post(
            "/api/networth/categories",
            json={
                "name": "Company Account",
                "category_type": "asset",
                "category_group": "investment",
                "is_personal": False,
                "display_order": 10,
            },
        )
        assert response.status_code == 201
        data = response.json

        assert data["is_personal"] is False
        assert data["display_order"] == 10

    def test_create_category_missing_name(self, client):
        """POST /api/networth/categories requires name."""
        response = client.post(
            "/api/networth/categories",
            json={"category_type": "asset", "category_group": "cash"},
        )
        assert response.status_code == 400
        assert "name" in response.json["error"].lower()

    def test_create_category_missing_type(self, client):
        """POST /api/networth/categories requires category_type."""
        response = client.post(
            "/api/networth/categories",
            json={"name": "Test", "category_group": "cash"},
        )
        assert response.status_code == 400
        assert "category_type" in response.json["error"].lower()

    def test_create_category_missing_group(self, client):
        """POST /api/networth/categories requires category_group."""
        response = client.post(
            "/api/networth/categories",
            json={"name": "Test", "category_type": "asset"},
        )
        assert response.status_code == 400
        assert "category_group" in response.json["error"].lower()

    def test_create_category_invalid_type(self, client):
        """POST /api/networth/categories validates category_type."""
        response = client.post(
            "/api/networth/categories",
            json={"name": "Test", "category_type": "invalid", "category_group": "cash"},
        )
        assert response.status_code == 400
        assert "category_type" in response.json["error"].lower()

    def test_create_category_invalid_group(self, client):
        """POST /api/networth/categories validates category_group."""
        response = client.post(
            "/api/networth/categories",
            json={
                "name": "Test",
                "category_type": "asset",
                "category_group": "invalid",
            },
        )
        assert response.status_code == 400
        assert "category_group" in response.json["error"].lower()

    def test_create_category_name_too_long(self, client):
        """POST /api/networth/categories rejects name > 100 chars."""
        response = client.post(
            "/api/networth/categories",
            json={
                "name": "x" * 101,
                "category_type": "asset",
                "category_group": "cash",
            },
        )
        assert response.status_code == 400

    def test_create_category_no_body(self, client):
        """POST /api/networth/categories with no body returns 400."""
        response = client.post(
            "/api/networth/categories", content_type="application/json"
        )
        assert response.status_code == 400


class TestCategoryUpdate:
    """Tests for updating categories."""

    def test_update_category(self, client):
        """PUT /api/networth/categories/<id> updates category."""
        create_response = client.post(
            "/api/networth/categories",
            json={
                "name": "Old Name",
                "category_type": "asset",
                "category_group": "cash",
            },
        )
        category_id = create_response.json["id"]

        response = client.put(
            f"/api/networth/categories/{category_id}",
            json={"name": "New Name", "display_order": 5},
        )
        assert response.status_code == 200
        assert response.json["name"] == "New Name"
        assert response.json["display_order"] == 5

    def test_update_category_not_found(self, client):
        """PUT /api/networth/categories/<id> returns 404 for non-existent."""
        response = client.put("/api/networth/categories/999", json={"name": "Test"})
        assert response.status_code == 404

    def test_update_category_no_body(self, client):
        """PUT /api/networth/categories/<id> with no body returns 400."""
        create_response = client.post(
            "/api/networth/categories",
            json={"name": "Test", "category_type": "asset", "category_group": "cash"},
        )
        category_id = create_response.json["id"]

        response = client.put(
            f"/api/networth/categories/{category_id}",
            content_type="application/json",
        )
        assert response.status_code == 400


class TestCategoryDelete:
    """Tests for deleting categories."""

    def test_delete_category(self, client):
        """DELETE /api/networth/categories/<id> removes category."""
        create_response = client.post(
            "/api/networth/categories",
            json={"name": "Test", "category_type": "asset", "category_group": "cash"},
        )
        category_id = create_response.json["id"]

        response = client.delete(f"/api/networth/categories/{category_id}")
        assert response.status_code == 200

        # Verify it's gone
        list_response = client.get("/api/networth/categories")
        assert len(list_response.json) == 0

    def test_delete_category_not_found(self, client):
        """DELETE /api/networth/categories/<id> returns 404 for non-existent."""
        response = client.delete("/api/networth/categories/999")
        assert response.status_code == 404

    def test_delete_category_in_use(self, client):
        """DELETE /api/networth/categories/<id> fails if category is used."""
        # Create category
        cat_response = client.post(
            "/api/networth/categories",
            json={"name": "Cash", "category_type": "asset", "category_group": "cash"},
        )
        category_id = cat_response.json["id"]

        # Create snapshot using this category
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [{"category_id": category_id, "amount": 1000}],
            },
        )

        # Try to delete category
        response = client.delete(f"/api/networth/categories/{category_id}")
        assert response.status_code == 409
        assert "used in" in response.json["error"].lower()


class TestCategorySeed:
    """Tests for seeding categories."""

    def test_seed_categories(self, client):
        """POST /api/networth/categories/seed creates default categories."""
        response = client.post("/api/networth/categories/seed")
        assert response.status_code == 201
        assert response.json["count"] == 11

    def test_seed_categories_already_exists(self, client):
        """POST /api/networth/categories/seed fails if categories exist."""
        client.post("/api/networth/categories/seed")

        response = client.post("/api/networth/categories/seed")
        assert response.status_code == 409


# =============================================================================
# Snapshot Tests
# =============================================================================


@pytest.fixture
def seeded_categories(client):
    """Fixture that seeds default categories and returns category lookup."""
    client.post("/api/networth/categories/seed")
    response = client.get("/api/networth/categories")
    return {c["name"]: c for c in response.json}


class TestSnapshotList:
    """Tests for listing snapshots."""

    def test_list_snapshots_empty(self, client):
        """GET /api/networth returns empty list initially."""
        response = client.get("/api/networth")
        assert response.status_code == 200
        assert response.json == []

    def test_list_snapshots_sorted_desc(self, client, seeded_categories):
        """GET /api/networth returns snapshots sorted by date descending."""
        cats = seeded_categories
        cash_id = cats["Cash"]["id"]

        client.post(
            "/api/networth",
            json={
                "month": 3,
                "year": 2024,
                "entries": [{"category_id": cash_id, "amount": 1000}],
            },
        )
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [{"category_id": cash_id, "amount": 500}],
            },
        )
        client.post(
            "/api/networth",
            json={
                "month": 2,
                "year": 2024,
                "entries": [{"category_id": cash_id, "amount": 750}],
            },
        )

        response = client.get("/api/networth")
        assert response.status_code == 200
        data = response.json

        assert len(data) == 3
        assert data[0]["month"] == 3
        assert data[1]["month"] == 2
        assert data[2]["month"] == 1


class TestSnapshotGet:
    """Tests for getting specific snapshot."""

    def test_get_snapshot_by_year_month(self, client, seeded_categories):
        """GET /api/networth/<year>/<month> returns specific snapshot."""
        cash_id = seeded_categories["Cash"]["id"]
        client.post(
            "/api/networth",
            json={
                "month": 6,
                "year": 2024,
                "entries": [{"category_id": cash_id, "amount": 5000}],
            },
        )

        response = client.get("/api/networth/2024/6")
        assert response.status_code == 200
        data = response.json

        assert data["month"] == 6
        assert data["year"] == 2024
        assert len(data["entries"]) == 1
        assert data["entries"][0]["amount"] == 5000.0

    def test_get_snapshot_not_found(self, client):
        """GET /api/networth/<year>/<month> returns 404 for non-existent."""
        response = client.get("/api/networth/2024/1")
        assert response.status_code == 404

    def test_get_snapshot_invalid_month(self, client):
        """GET /api/networth/<year>/<month> validates month range."""
        response = client.get("/api/networth/2024/13")
        assert response.status_code == 400

        response = client.get("/api/networth/2024/0")
        assert response.status_code == 400


class TestSnapshotCreate:
    """Tests for creating snapshots."""

    def test_create_snapshot_minimal(self, client):
        """POST /api/networth creates snapshot with just month/year."""
        response = client.post("/api/networth", json={"month": 1, "year": 2024})
        assert response.status_code == 201
        data = response.json

        assert data["month"] == 1
        assert data["year"] == 2024
        assert data["entries"] == []
        assert data["net_worth"] == 0.0
        assert "id" in data
        assert "timestamp" in data

    def test_create_snapshot_with_entries(self, client, seeded_categories):
        """POST /api/networth creates snapshot with entries."""
        cats = seeded_categories
        response = client.post(
            "/api/networth",
            json={
                "month": 6,
                "year": 2024,
                "entries": [
                    {"category_id": cats["Cash"]["id"], "amount": 5000},
                    {"category_id": cats["Savings"]["id"], "amount": 10000},
                    {"category_id": cats["Student Loan"]["id"], "amount": -5000},
                ],
            },
        )
        assert response.status_code == 201
        data = response.json

        assert len(data["entries"]) == 3
        assert data["total_assets"] == 15000.0
        assert data["total_liabilities"] == -5000.0
        assert data["net_worth"] == 10000.0

    def test_create_snapshot_missing_month(self, client):
        """POST /api/networth requires month."""
        response = client.post("/api/networth", json={"year": 2024})
        assert response.status_code == 400
        assert "month" in response.json["error"].lower()

    def test_create_snapshot_missing_year(self, client):
        """POST /api/networth requires year."""
        response = client.post("/api/networth", json={"month": 1})
        assert response.status_code == 400
        assert "year" in response.json["error"].lower()

    def test_create_snapshot_invalid_month(self, client):
        """POST /api/networth validates month range."""
        response = client.post("/api/networth", json={"month": 13, "year": 2024})
        assert response.status_code == 400

        response = client.post("/api/networth", json={"month": 0, "year": 2024})
        assert response.status_code == 400

    def test_create_snapshot_duplicate(self, client):
        """POST /api/networth rejects duplicate year/month."""
        client.post("/api/networth", json={"month": 1, "year": 2024})

        response = client.post("/api/networth", json={"month": 1, "year": 2024})
        assert response.status_code == 409

    def test_create_snapshot_invalid_category(self, client):
        """POST /api/networth rejects invalid category_id."""
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [{"category_id": 999, "amount": 1000}],
            },
        )
        assert response.status_code == 400
        assert "category" in response.json["error"].lower()

    def test_create_snapshot_amount_exceeds_max(self, client, seeded_categories):
        """POST /api/networth rejects amount > 1 billion."""
        cash_id = seeded_categories["Cash"]["id"]
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [{"category_id": cash_id, "amount": 1_000_000_001}],
            },
        )
        assert response.status_code == 400
        assert "exceeds" in response.json["error"].lower()

    def test_create_snapshot_no_body(self, client):
        """POST /api/networth with no body returns 400."""
        response = client.post("/api/networth", content_type="application/json")
        assert response.status_code == 400


class TestSnapshotUpdate:
    """Tests for updating snapshots."""

    def test_update_snapshot_entries(self, client, seeded_categories):
        """PUT /api/networth/<id> updates entries."""
        cats = seeded_categories
        create_response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [{"category_id": cats["Cash"]["id"], "amount": 1000}],
            },
        )
        snapshot_id = create_response.json["id"]

        response = client.put(
            f"/api/networth/{snapshot_id}",
            json={
                "entries": [
                    {"category_id": cats["Cash"]["id"], "amount": 2000},
                    {"category_id": cats["Savings"]["id"], "amount": 5000},
                ]
            },
        )
        assert response.status_code == 200
        data = response.json

        assert len(data["entries"]) == 2
        assert data["net_worth"] == 7000.0

    def test_update_snapshot_not_found(self, client):
        """PUT /api/networth/<id> returns 404 for non-existent."""
        response = client.put("/api/networth/999", json={"entries": []})
        assert response.status_code == 404

    def test_update_snapshot_change_month_year(self, client):
        """PUT /api/networth/<id> can change month/year if no conflict."""
        create_response = client.post("/api/networth", json={"month": 1, "year": 2024})
        snapshot_id = create_response.json["id"]

        response = client.put(
            f"/api/networth/{snapshot_id}", json={"month": 2, "year": 2024}
        )
        assert response.status_code == 200
        assert response.json["month"] == 2

    def test_update_snapshot_month_year_conflict(self, client):
        """PUT /api/networth/<id> rejects if new month/year would conflict."""
        client.post("/api/networth", json={"month": 1, "year": 2024})
        create_response = client.post("/api/networth", json={"month": 2, "year": 2024})
        snapshot_id = create_response.json["id"]

        response = client.put(
            f"/api/networth/{snapshot_id}", json={"month": 1, "year": 2024}
        )
        assert response.status_code == 409


class TestSnapshotDelete:
    """Tests for deleting snapshots."""

    def test_delete_snapshot(self, client):
        """DELETE /api/networth/<id> removes snapshot."""
        create_response = client.post("/api/networth", json={"month": 1, "year": 2024})
        snapshot_id = create_response.json["id"]

        response = client.delete(f"/api/networth/{snapshot_id}")
        assert response.status_code == 200

        # Verify it's gone
        list_response = client.get("/api/networth")
        assert len(list_response.json) == 0

    def test_delete_snapshot_not_found(self, client):
        """DELETE /api/networth/<id> returns 404 for non-existent."""
        response = client.delete("/api/networth/999")
        assert response.status_code == 404

    def test_delete_snapshot_cascades_entries(self, client, seeded_categories):
        """DELETE /api/networth/<id> also deletes associated entries."""
        cash_id = seeded_categories["Cash"]["id"]
        create_response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [{"category_id": cash_id, "amount": 1000}],
            },
        )
        snapshot_id = create_response.json["id"]

        # Delete snapshot
        client.delete(f"/api/networth/{snapshot_id}")

        # Category should still be deletable (entries were cascaded)
        response = client.delete(f"/api/networth/categories/{cash_id}")
        assert response.status_code == 200


# =============================================================================
# Calculation Tests
# =============================================================================


class TestNetWorthCalculations:
    """Tests for net worth derived field calculations."""

    def test_total_assets_calculation(self, client, seeded_categories):
        """Net worth correctly calculates total assets."""
        cats = seeded_categories
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [
                    {"category_id": cats["Cash"]["id"], "amount": 1000},
                    {"category_id": cats["Savings"]["id"], "amount": 2000},
                    {
                        "category_id": cats["Personal Investments"]["id"],
                        "amount": 10000,
                    },
                ],
            },
        )
        assert response.status_code == 201
        assert response.json["total_assets"] == 13000.0

    def test_total_liabilities_calculation(self, client, seeded_categories):
        """Net worth correctly calculates total liabilities."""
        cats = seeded_categories
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [
                    {"category_id": cats["Student Loan"]["id"], "amount": -10000},
                    {"category_id": cats["Credit Cards"]["id"], "amount": -500},
                ],
            },
        )
        assert response.status_code == 201
        assert response.json["total_liabilities"] == -10500.0

    def test_net_worth_calculation(self, client, seeded_categories):
        """Net worth is total_assets + total_liabilities."""
        cats = seeded_categories
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [
                    {"category_id": cats["Cash"]["id"], "amount": 5000},
                    {"category_id": cats["Savings"]["id"], "amount": 10000},
                    {"category_id": cats["Student Loan"]["id"], "amount": -3000},
                ],
            },
        )
        assert response.status_code == 201
        data = response.json

        assert data["total_assets"] == 15000.0
        assert data["total_liabilities"] == -3000.0
        assert data["net_worth"] == 12000.0

    def test_personal_wealth_calculation(self, client, seeded_categories):
        """Personal wealth includes personal assets + liabilities."""
        cats = seeded_categories
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [
                    {"category_id": cats["Cash"]["id"], "amount": 1000},  # personal
                    {
                        "category_id": cats["Personal Investments"]["id"],
                        "amount": 5000,
                    },  # personal
                    {
                        "category_id": cats["Company Investments"]["id"],
                        "amount": 10000,
                    },  # NOT personal
                    {
                        "category_id": cats["Student Loan"]["id"],
                        "amount": -2000,
                    },  # personal liability
                ],
            },
        )
        assert response.status_code == 201
        data = response.json

        # Personal = 1000 + 5000 - 2000 = 4000
        assert data["personal_wealth"] == 4000.0

    def test_company_wealth_calculation(self, client, seeded_categories):
        """Company wealth includes only company assets."""
        cats = seeded_categories
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [
                    {"category_id": cats["Cash"]["id"], "amount": 5000},  # personal
                    {"category_id": cats["Company Investments"]["id"], "amount": 10000},
                    {"category_id": cats["Company Checkings"]["id"], "amount": 3000},
                ],
            },
        )
        assert response.status_code == 201
        assert response.json["company_wealth"] == 13000.0

    def test_group_totals_and_percentages(self, client, seeded_categories):
        """Snapshot includes group totals and percentages."""
        cats = seeded_categories
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [
                    {"category_id": cats["Cash"]["id"], "amount": 5000},
                    {"category_id": cats["Personal Investments"]["id"], "amount": 5000},
                ],
            },
        )
        assert response.status_code == 201
        data = response.json

        # Total assets = 10000
        assert data["by_group"]["cash"] == 5000.0
        assert data["by_group"]["investment"] == 5000.0
        assert data["percentages"]["cash_pct"] == 50.0
        assert data["percentages"]["investment_pct"] == 50.0

    def test_percentages_zero_assets(self, client):
        """Percentage calculations handle zero assets."""
        response = client.post("/api/networth", json={"month": 1, "year": 2024})
        assert response.status_code == 201
        data = response.json

        assert data["percentages"] == {}

    def test_change_from_previous_first_month(self, client, seeded_categories):
        """First snapshot has 0 change_from_previous."""
        cash_id = seeded_categories["Cash"]["id"]
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [{"category_id": cash_id, "amount": 10000}],
            },
        )
        assert response.status_code == 201
        assert response.json["change_from_previous"] == 0

    def test_change_from_previous_subsequent_months(self, client, seeded_categories):
        """Subsequent snapshots show change from previous month."""
        cash_id = seeded_categories["Cash"]["id"]

        # January: 10000 net worth
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [{"category_id": cash_id, "amount": 10000}],
            },
        )

        # February: 12500 net worth
        response = client.post(
            "/api/networth",
            json={
                "month": 2,
                "year": 2024,
                "entries": [{"category_id": cash_id, "amount": 12500}],
            },
        )
        assert response.status_code == 201
        assert response.json["change_from_previous"] == 2500.0

    def test_change_from_previous_year_boundary(self, client, seeded_categories):
        """Change calculation works across year boundary."""
        cash_id = seeded_categories["Cash"]["id"]

        # December 2023: 50000
        client.post(
            "/api/networth",
            json={
                "month": 12,
                "year": 2023,
                "entries": [{"category_id": cash_id, "amount": 50000}],
            },
        )

        # January 2024: 52000
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [{"category_id": cash_id, "amount": 52000}],
            },
        )
        assert response.status_code == 201
        assert response.json["change_from_previous"] == 2000.0


# =============================================================================
# Seed Tests
# =============================================================================


class TestNetWorthSeed:
    """Tests for net worth seed endpoint."""

    def test_seed_requires_categories(self, client):
        """POST /api/networth/seed fails without categories."""
        response = client.post("/api/networth/seed")
        assert response.status_code == 400
        assert "categories" in response.json["error"].lower()

    def test_seed_creates_data(self, client, seeded_categories):
        """POST /api/networth/seed creates example data."""
        response = client.post("/api/networth/seed")
        assert response.status_code == 201
        assert response.json["count"] == 12

    def test_seed_creates_12_months(self, client, seeded_categories):
        """POST /api/networth/seed creates exactly 12 months."""
        client.post("/api/networth/seed")

        response = client.get("/api/networth")
        assert len(response.json) == 12

    def test_seed_data_has_growth(self, client, seeded_categories):
        """Seeded data shows growth over time."""
        client.post("/api/networth/seed")

        response = client.get("/api/networth")
        data = response.json

        # Data is sorted desc, so first is most recent
        first_month = data[-1]  # January (oldest)
        last_month = data[0]  # December (newest)

        assert last_month["net_worth"] > first_month["net_worth"]

    def test_seed_rejects_if_data_exists(self, client, seeded_categories):
        """POST /api/networth/seed fails if data already exists."""
        client.post("/api/networth/seed")

        response = client.post("/api/networth/seed")
        assert response.status_code == 409

    def test_seed_calculates_derived_fields(self, client, seeded_categories):
        """Seeded data has all derived fields calculated."""
        client.post("/api/networth/seed")

        # Get a mid-year snapshot
        response = client.get("/api/networth")
        data = response.json
        june = next(s for s in data if s["month"] == 6)

        # Check that calculated fields are populated
        assert june["total_assets"] > 0
        assert june["net_worth"] > 0
        assert "investment" in june["by_group"]
        assert "cash" in june["by_group"]


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_list_sorted_across_years(self, client, seeded_categories):
        """GET /api/networth sorts correctly across year boundaries."""
        cash_id = seeded_categories["Cash"]["id"]
        client.post(
            "/api/networth",
            json={
                "month": 12,
                "year": 2023,
                "entries": [{"category_id": cash_id, "amount": 1000}],
            },
        )
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [{"category_id": cash_id, "amount": 1000}],
            },
        )
        client.post(
            "/api/networth",
            json={
                "month": 11,
                "year": 2023,
                "entries": [{"category_id": cash_id, "amount": 1000}],
            },
        )

        response = client.get("/api/networth")
        data = response.json

        assert len(data) == 3
        # Most recent first
        assert data[0]["year"] == 2024 and data[0]["month"] == 1
        assert data[1]["year"] == 2023 and data[1]["month"] == 12
        assert data[2]["year"] == 2023 and data[2]["month"] == 11

    def test_change_from_previous_gap_in_months(self, client, seeded_categories):
        """change_from_previous is 0 when previous month is missing."""
        cash_id = seeded_categories["Cash"]["id"]

        # Only create January and March (skip February)
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [{"category_id": cash_id, "amount": 10000}],
            },
        )

        response = client.post(
            "/api/networth",
            json={
                "month": 3,
                "year": 2024,
                "entries": [{"category_id": cash_id, "amount": 15000}],
            },
        )
        # March should not find February
        assert response.json["change_from_previous"] == 0

    def test_zero_net_worth(self, client, seeded_categories):
        """Handles zero net worth correctly (assets = liabilities)."""
        cats = seeded_categories
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [
                    {"category_id": cats["Cash"]["id"], "amount": 5000},
                    {"category_id": cats["Student Loan"]["id"], "amount": -5000},
                ],
            },
        )
        assert response.status_code == 201
        assert response.json["net_worth"] == 0

    def test_negative_net_worth(self, client, seeded_categories):
        """Handles negative net worth (liabilities > assets)."""
        cats = seeded_categories
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [
                    {"category_id": cats["Cash"]["id"], "amount": 2000},
                    {"category_id": cats["Student Loan"]["id"], "amount": -10000},
                ],
            },
        )
        assert response.status_code == 201
        assert response.json["net_worth"] == -8000.0

    def test_only_liabilities(self, client, seeded_categories):
        """Handles snapshot with only liabilities."""
        cats = seeded_categories
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [
                    {"category_id": cats["Student Loan"]["id"], "amount": -15000},
                    {"category_id": cats["Credit Cards"]["id"], "amount": -2000},
                ],
            },
        )
        assert response.status_code == 201
        assert response.json["total_assets"] == 0
        assert response.json["total_liabilities"] == -17000.0
        assert response.json["net_worth"] == -17000.0

    def test_decimal_precision(self, client, seeded_categories):
        """Amounts preserve decimal precision."""
        cash_id = seeded_categories["Cash"]["id"]
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [{"category_id": cash_id, "amount": 1234.56}],
            },
        )
        assert response.status_code == 201
        assert response.json["entries"][0]["amount"] == 1234.56

    def test_string_amount_conversion(self, client, seeded_categories):
        """String amounts are converted correctly."""
        cash_id = seeded_categories["Cash"]["id"]
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [{"category_id": cash_id, "amount": "5000.50"}],
            },
        )
        assert response.status_code == 201
        assert response.json["entries"][0]["amount"] == 5000.50

    def test_very_large_amounts(self, client, seeded_categories):
        """Handles very large (but valid) amounts."""
        cash_id = seeded_categories["Cash"]["id"]
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [{"category_id": cash_id, "amount": 999_999_999.99}],
            },
        )
        assert response.status_code == 201
        assert response.json["entries"][0]["amount"] == 999_999_999.99

    def test_change_from_previous_negative(self, client, seeded_categories):
        """change_from_previous can be negative (wealth decreased)."""
        cash_id = seeded_categories["Cash"]["id"]
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [{"category_id": cash_id, "amount": 20000}],
            },
        )

        response = client.post(
            "/api/networth",
            json={
                "month": 2,
                "year": 2024,
                "entries": [{"category_id": cash_id, "amount": 15000}],
            },
        )
        assert response.json["change_from_previous"] == -5000.0

    def test_update_recalculates_next_month(self, client, seeded_categories):
        """Updating a snapshot recalculates next month's change_from_previous."""
        cash_id = seeded_categories["Cash"]["id"]

        # Create January: 10000
        jan_response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [{"category_id": cash_id, "amount": 10000}],
            },
        )
        jan_id = jan_response.json["id"]

        # Create February: 15000 (change = +5000)
        feb_response = client.post(
            "/api/networth",
            json={
                "month": 2,
                "year": 2024,
                "entries": [{"category_id": cash_id, "amount": 15000}],
            },
        )
        assert feb_response.json["change_from_previous"] == 5000.0

        # Update January to 12000
        client.put(
            f"/api/networth/{jan_id}",
            json={"entries": [{"category_id": cash_id, "amount": 12000}]},
        )

        # February's change should now be 15000 - 12000 = 3000
        feb_check = client.get("/api/networth/2024/2")
        assert feb_check.json["change_from_previous"] == 3000.0

    def test_update_recalculates_across_year_boundary(self, client, seeded_categories):
        """Updating December recalculates January's change_from_previous."""
        cash_id = seeded_categories["Cash"]["id"]

        # Create December 2023: 50000
        dec_response = client.post(
            "/api/networth",
            json={
                "month": 12,
                "year": 2023,
                "entries": [{"category_id": cash_id, "amount": 50000}],
            },
        )
        dec_id = dec_response.json["id"]

        # Create January 2024: 55000 (change = +5000)
        jan_response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "entries": [{"category_id": cash_id, "amount": 55000}],
            },
        )
        assert jan_response.json["change_from_previous"] == 5000.0

        # Update December to 52000
        client.put(
            f"/api/networth/{dec_id}",
            json={"entries": [{"category_id": cash_id, "amount": 52000}]},
        )

        # January's change should now be 55000 - 52000 = 3000
        jan_check = client.get("/api/networth/2024/1")
        assert jan_check.json["change_from_previous"] == 3000.0


class TestDisplayOrderValidation:
    """Tests for display_order validation."""

    def test_create_category_invalid_display_order(self, client):
        """POST /api/networth/categories rejects non-integer display_order."""
        response = client.post(
            "/api/networth/categories",
            json={
                "name": "Test",
                "category_type": "asset",
                "category_group": "cash",
                "display_order": "not_an_int",
            },
        )
        assert response.status_code == 400
        assert "display_order" in response.json["error"].lower()

    def test_update_category_invalid_display_order(self, client):
        """PUT /api/networth/categories/<id> rejects non-integer display_order."""
        create_response = client.post(
            "/api/networth/categories",
            json={"name": "Test", "category_type": "asset", "category_group": "cash"},
        )
        category_id = create_response.json["id"]

        response = client.put(
            f"/api/networth/categories/{category_id}",
            json={"display_order": "invalid"},
        )
        assert response.status_code == 400
        assert "display_order" in response.json["error"].lower()
