"""Tests for net worth API endpoints."""


class TestNetWorthValidation:
    """Tests for input validation edge cases."""

    def test_create_no_body(self, client):
        """POST /api/networth with no JSON body returns 400."""
        response = client.post("/api/networth", content_type="application/json")
        assert response.status_code == 400

    def test_create_invalid_month_type(self, client):
        """POST /api/networth with non-integer month returns 400."""
        response = client.post("/api/networth", json={"month": "january", "year": 2024})
        assert response.status_code == 400

    def test_create_invalid_year_type(self, client):
        """POST /api/networth with non-integer year returns 400."""
        response = client.post("/api/networth", json={"month": 1, "year": "2024"})
        # String "2024" should be converted to int, so this should work
        assert response.status_code == 201

    def test_create_invalid_amount_type(self, client):
        """POST /api/networth with non-numeric amount returns 400."""
        response = client.post(
            "/api/networth", json={"month": 1, "year": 2024, "cash": "invalid"}
        )
        assert response.status_code == 400
        assert "must be a number" in response.json["error"].lower()

    def test_create_negative_amount_allowed(self, client):
        """POST /api/networth allows negative amounts for liabilities."""
        response = client.post(
            "/api/networth",
            json={"month": 1, "year": 2024, "student_loan": -50000},
        )
        assert response.status_code == 201
        assert response.json["student_loan"] == -50000.0

    def test_create_large_negative_amount_rejected(self, client):
        """POST /api/networth rejects amounts exceeding max (negative)."""
        response = client.post(
            "/api/networth",
            json={"month": 1, "year": 2024, "student_loan": -1_000_000_001},
        )
        assert response.status_code == 400
        assert "exceeds maximum" in response.json["error"].lower()

    def test_update_no_body(self, client):
        """PUT /api/networth/<id> with no JSON body returns 400."""
        create_response = client.post("/api/networth", json={"month": 1, "year": 2024})
        snapshot_id = create_response.json["id"]

        response = client.put(
            f"/api/networth/{snapshot_id}", content_type="application/json"
        )
        assert response.status_code == 400

    def test_update_invalid_amount_type(self, client):
        """PUT /api/networth/<id> with non-numeric amount returns 400."""
        create_response = client.post("/api/networth", json={"month": 1, "year": 2024})
        snapshot_id = create_response.json["id"]

        response = client.put(
            f"/api/networth/{snapshot_id}", json={"cash": "not_a_number"}
        )
        assert response.status_code == 400

    def test_update_invalid_month_on_change(self, client):
        """PUT /api/networth/<id> rejects invalid month when changing."""
        create_response = client.post("/api/networth", json={"month": 1, "year": 2024})
        snapshot_id = create_response.json["id"]

        response = client.put(f"/api/networth/{snapshot_id}", json={"month": 13})
        assert response.status_code == 400

    def test_decimal_precision(self, client):
        """POST /api/networth handles decimal amounts correctly."""
        response = client.post(
            "/api/networth",
            json={"month": 1, "year": 2024, "cash": 1234.56},
        )
        assert response.status_code == 201
        assert response.json["cash"] == 1234.56

    def test_float_string_conversion(self, client):
        """POST /api/networth accepts string numbers."""
        response = client.post(
            "/api/networth",
            json={"month": 1, "year": 2024, "cash": "5000.50"},
        )
        assert response.status_code == 201
        assert response.json["cash"] == 5000.50


class TestNetWorthList:
    """Tests for listing net worth snapshots."""

    def test_list_snapshots_empty(self, client):
        """GET /api/networth returns empty list initially."""
        response = client.get("/api/networth")
        assert response.status_code == 200
        assert response.json == []

    def test_list_snapshots_sorted_desc(self, client):
        """GET /api/networth returns snapshots sorted by date descending."""
        # Create snapshots out of order
        client.post("/api/networth", json={"month": 3, "year": 2024, "cash": 1000})
        client.post("/api/networth", json={"month": 1, "year": 2024, "cash": 500})
        client.post("/api/networth", json={"month": 2, "year": 2024, "cash": 750})

        response = client.get("/api/networth")
        assert response.status_code == 200
        data = response.json

        assert len(data) == 3
        # Should be sorted by year desc, month desc
        assert data[0]["month"] == 3
        assert data[1]["month"] == 2
        assert data[2]["month"] == 1


class TestNetWorthGet:
    """Tests for getting specific snapshot."""

    def test_get_snapshot_by_year_month(self, client):
        """GET /api/networth/<year>/<month> returns specific snapshot."""
        client.post("/api/networth", json={"month": 6, "year": 2024, "cash": 5000})

        response = client.get("/api/networth/2024/6")
        assert response.status_code == 200
        data = response.json

        assert data["month"] == 6
        assert data["year"] == 2024
        assert data["cash"] == 5000.0

    def test_get_snapshot_not_found(self, client):
        """GET /api/networth/<year>/<month> returns 404 for non-existent snapshot."""
        response = client.get("/api/networth/2024/1")
        assert response.status_code == 404
        assert "not found" in response.json["error"].lower()

    def test_get_snapshot_invalid_month(self, client):
        """GET /api/networth/<year>/<month> validates month range."""
        response = client.get("/api/networth/2024/13")
        assert response.status_code == 400

        response = client.get("/api/networth/2024/0")
        assert response.status_code == 400


class TestNetWorthCreate:
    """Tests for creating net worth snapshots."""

    def test_create_snapshot_minimal(self, client):
        """POST /api/networth creates snapshot with just month/year."""
        response = client.post("/api/networth", json={"month": 1, "year": 2024})
        assert response.status_code == 201
        data = response.json

        assert data["month"] == 1
        assert data["year"] == 2024
        assert data["cash"] == 0.0
        assert data["net_worth"] == 0.0
        assert "id" in data
        assert "timestamp" in data

    def test_create_snapshot_full(self, client):
        """POST /api/networth creates snapshot with all fields."""
        response = client.post(
            "/api/networth",
            json={
                "month": 6,
                "year": 2024,
                "cash": 5000,
                "savings": 10000,
                "rent_account": 1500,
                "crypto": 3000,
                "house_worth": 0,
                "personal_investments": 25000,
                "personal_bonds": 5000,
                "company_investments": 8000,
                "company_checkings": 2000,
                "student_loan": -5000,
                "credit_cards": -500,
            },
        )
        assert response.status_code == 201
        data = response.json

        assert data["cash"] == 5000.0
        assert data["savings"] == 10000.0
        assert data["student_loan"] == -5000.0
        assert data["credit_cards"] == -500.0

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
        assert "month" in response.json["error"].lower()

        response = client.post("/api/networth", json={"month": 0, "year": 2024})
        assert response.status_code == 400

    def test_create_snapshot_duplicate(self, client):
        """POST /api/networth rejects duplicate year/month."""
        client.post("/api/networth", json={"month": 1, "year": 2024})

        response = client.post("/api/networth", json={"month": 1, "year": 2024})
        assert response.status_code == 409
        assert "already exists" in response.json["error"].lower()

    def test_create_snapshot_validates_amount(self, client):
        """POST /api/networth validates amount values."""
        response = client.post(
            "/api/networth",
            json={"month": 1, "year": 2024, "cash": 1_000_000_001},
        )
        assert response.status_code == 400
        assert "exceeds maximum" in response.json["error"].lower()


class TestNetWorthUpdate:
    """Tests for updating net worth snapshots."""

    def test_update_snapshot(self, client):
        """PUT /api/networth/<id> updates snapshot."""
        create_response = client.post(
            "/api/networth", json={"month": 1, "year": 2024, "cash": 1000}
        )
        snapshot_id = create_response.json["id"]

        response = client.put(
            f"/api/networth/{snapshot_id}", json={"cash": 2000, "savings": 5000}
        )
        assert response.status_code == 200
        data = response.json

        assert data["cash"] == 2000.0
        assert data["savings"] == 5000.0

    def test_update_snapshot_not_found(self, client):
        """PUT /api/networth/<id> returns 404 for non-existent snapshot."""
        response = client.put("/api/networth/999", json={"cash": 1000})
        assert response.status_code == 404

    def test_update_snapshot_recalculates(self, client):
        """PUT /api/networth/<id> recalculates derived fields."""
        create_response = client.post(
            "/api/networth",
            json={"month": 1, "year": 2024, "cash": 1000, "savings": 2000},
        )
        snapshot_id = create_response.json["id"]
        original_net_worth = create_response.json["net_worth"]

        response = client.put(f"/api/networth/{snapshot_id}", json={"cash": 5000})
        assert response.status_code == 200
        assert response.json["net_worth"] != original_net_worth
        assert response.json["net_worth"] == 7000.0  # 5000 + 2000

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


class TestNetWorthDelete:
    """Tests for deleting net worth snapshots."""

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
        """DELETE /api/networth/<id> returns 404 for non-existent snapshot."""
        response = client.delete("/api/networth/999")
        assert response.status_code == 404


class TestNetWorthCalculations:
    """Tests for net worth derived field calculations."""

    def test_total_assets_calculation(self, client):
        """Net worth correctly calculates total assets."""
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "cash": 1000,
                "savings": 2000,
                "rent_account": 500,
                "crypto": 1500,
                "house_worth": 100000,
                "personal_investments": 10000,
                "personal_bonds": 3000,
                "company_investments": 5000,
                "company_checkings": 2000,
            },
        )
        assert response.status_code == 201
        data = response.json

        expected_assets = 1000 + 2000 + 500 + 1500 + 100000 + 10000 + 3000 + 5000 + 2000
        assert data["total_assets"] == expected_assets

    def test_total_liabilities_calculation(self, client):
        """Net worth correctly calculates total liabilities."""
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "student_loan": -10000,
                "credit_cards": -500,
            },
        )
        assert response.status_code == 201
        data = response.json

        assert data["total_liabilities"] == -10500

    def test_net_worth_calculation(self, client):
        """Net worth is total_assets + total_liabilities."""
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "cash": 5000,
                "savings": 10000,
                "student_loan": -3000,
            },
        )
        assert response.status_code == 201
        data = response.json

        # 15000 assets - 3000 liabilities = 12000 net worth
        assert data["total_assets"] == 15000
        assert data["total_liabilities"] == -3000
        assert data["net_worth"] == 12000

    def test_personal_wealth_calculation(self, client):
        """Personal wealth includes personal assets plus liabilities."""
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "cash": 1000,
                "savings": 2000,
                "rent_account": 500,
                "crypto": 1500,
                "personal_investments": 5000,
                "personal_bonds": 1000,
                "company_investments": 10000,  # Not included in personal
                "company_checkings": 5000,  # Not included in personal
                "student_loan": -2000,
            },
        )
        assert response.status_code == 201
        data = response.json

        # Personal = 1000 + 2000 + 500 + 1500 + 5000 + 1000 - 2000 = 9000
        expected_personal = 1000 + 2000 + 500 + 1500 + 5000 + 1000 - 2000
        assert data["personal_wealth"] == expected_personal

    def test_company_wealth_calculation(self, client):
        """Company wealth includes only company assets."""
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "cash": 5000,  # Not company
                "company_investments": 10000,
                "company_checkings": 3000,
            },
        )
        assert response.status_code == 201
        data = response.json

        assert data["company_wealth"] == 13000

    def test_total_investments_calculation(self, client):
        """Total investments includes personal and company investments."""
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "personal_investments": 15000,
                "company_investments": 8000,
                "personal_bonds": 5000,  # Not counted as investments
            },
        )
        assert response.status_code == 201
        data = response.json

        assert data["total_investments"] == 23000

    def test_percentage_calculations(self, client):
        """Percentage calculations are correct."""
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "cash": 2000,
                "savings": 3000,
                "crypto": 2500,
                "personal_investments": 7500,
                "company_investments": 2500,
                "company_checkings": 2500,
            },
        )
        assert response.status_code == 201
        data = response.json

        # Total assets = 20000
        # stocks_pct = (7500 + 2500) / 20000 * 100 = 50%
        # crypto_pct = 2500 / 20000 * 100 = 12.5%
        # cash_pct = (2000 + 3000 + 2500) / 20000 * 100 = 37.5%
        assert data["stocks_pct"] == 50.0
        assert data["crypto_pct"] == 12.5
        assert data["cash_pct"] == 37.5

    def test_percentage_zero_assets(self, client):
        """Percentage calculations handle zero assets."""
        response = client.post("/api/networth", json={"month": 1, "year": 2024})
        assert response.status_code == 201
        data = response.json

        assert data["stocks_pct"] == 0
        assert data["crypto_pct"] == 0
        assert data["cash_pct"] == 0

    def test_change_from_previous_first_month(self, client):
        """First snapshot has 0 change_from_previous."""
        response = client.post(
            "/api/networth",
            json={"month": 1, "year": 2024, "cash": 10000},
        )
        assert response.status_code == 201
        assert response.json["change_from_previous"] == 0

    def test_change_from_previous_subsequent_months(self, client):
        """Subsequent snapshots show change from previous month."""
        # January: 10000 net worth
        client.post(
            "/api/networth",
            json={"month": 1, "year": 2024, "cash": 10000},
        )

        # February: 12500 net worth
        response = client.post(
            "/api/networth",
            json={"month": 2, "year": 2024, "cash": 12500},
        )
        assert response.status_code == 201
        assert response.json["change_from_previous"] == 2500

    def test_change_from_previous_year_boundary(self, client):
        """Change calculation works across year boundary."""
        # December 2023: 50000
        client.post(
            "/api/networth",
            json={"month": 12, "year": 2023, "cash": 50000},
        )

        # January 2024: 52000
        response = client.post(
            "/api/networth",
            json={"month": 1, "year": 2024, "cash": 52000},
        )
        assert response.status_code == 201
        assert response.json["change_from_previous"] == 2000


class TestNetWorthSeed:
    """Tests for net worth seed endpoint."""

    def test_seed_creates_data(self, client):
        """POST /api/networth/seed creates example data."""
        response = client.post("/api/networth/seed")
        assert response.status_code == 201
        data = response.json

        assert "message" in data
        assert data["count"] == 12

    def test_seed_creates_12_months(self, client):
        """POST /api/networth/seed creates exactly 12 months."""
        client.post("/api/networth/seed")

        response = client.get("/api/networth")
        assert len(response.json) == 12

    def test_seed_data_has_growth(self, client):
        """Seeded data shows growth over time."""
        client.post("/api/networth/seed")

        response = client.get("/api/networth")
        data = response.json

        # Data is sorted desc, so first is most recent
        first_month = data[-1]  # January (oldest)
        last_month = data[0]  # December (newest)

        assert last_month["net_worth"] > first_month["net_worth"]

    def test_seed_rejects_if_data_exists(self, client):
        """POST /api/networth/seed fails if data already exists."""
        client.post("/api/networth/seed")

        response = client.post("/api/networth/seed")
        assert response.status_code == 409
        assert "already exists" in response.json["error"].lower()

    def test_seed_calculates_derived_fields(self, client):
        """Seeded data has all derived fields calculated."""
        client.post("/api/networth/seed")

        response = client.get("/api/networth/2024/6")
        data = response.json

        # Check that calculated fields are populated
        assert data["total_assets"] > 0
        assert data["net_worth"] > 0
        assert data["stocks_pct"] > 0
        assert data["crypto_pct"] > 0
        assert data["cash_pct"] > 0

    def test_seed_change_from_previous_populated(self, client):
        """Seeded data has change_from_previous for all but first month."""
        client.post("/api/networth/seed")

        response = client.get("/api/networth")
        data = response.json

        # First month (oldest - January) should have 0 change
        january = next(s for s in data if s["month"] == 1 and s["year"] == 2024)
        assert january["change_from_previous"] == 0

        # Other months should have non-zero change
        february = next(s for s in data if s["month"] == 2 and s["year"] == 2024)
        assert february["change_from_previous"] != 0


class TestNetWorthEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_list_sorted_across_years(self, client):
        """GET /api/networth sorts correctly across year boundaries."""
        client.post("/api/networth", json={"month": 12, "year": 2023})
        client.post("/api/networth", json={"month": 1, "year": 2024})
        client.post("/api/networth", json={"month": 11, "year": 2023})

        response = client.get("/api/networth")
        data = response.json

        assert len(data) == 3
        # Most recent first: Jan 2024, Dec 2023, Nov 2023
        assert data[0]["year"] == 2024 and data[0]["month"] == 1
        assert data[1]["year"] == 2023 and data[1]["month"] == 12
        assert data[2]["year"] == 2023 and data[2]["month"] == 11

    def test_change_from_previous_gap_in_months(self, client):
        """change_from_previous is 0 when previous month is missing."""
        # Only create January and March (skip February)
        client.post("/api/networth", json={"month": 1, "year": 2024, "cash": 10000})

        response = client.post(
            "/api/networth", json={"month": 3, "year": 2024, "cash": 15000}
        )
        # March should not find February, so change_from_previous = 0
        assert response.json["change_from_previous"] == 0

    def test_update_recalculates_change_from_previous(self, client):
        """PUT recalculates change_from_previous based on current previous month."""
        client.post("/api/networth", json={"month": 1, "year": 2024, "cash": 10000})
        create_response = client.post(
            "/api/networth", json={"month": 2, "year": 2024, "cash": 12000}
        )
        snapshot_id = create_response.json["id"]
        assert create_response.json["change_from_previous"] == 2000

        # Update February's cash
        response = client.put(f"/api/networth/{snapshot_id}", json={"cash": 15000})
        # change_from_previous should now be 15000 - 10000 = 5000
        assert response.json["change_from_previous"] == 5000

    def test_zero_net_worth(self, client):
        """Handles zero net worth correctly (assets = liabilities)."""
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "cash": 5000,
                "student_loan": -5000,
            },
        )
        assert response.status_code == 201
        assert response.json["net_worth"] == 0
        assert response.json["total_assets"] == 5000
        assert response.json["total_liabilities"] == -5000

    def test_negative_net_worth(self, client):
        """Handles negative net worth (liabilities > assets)."""
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "cash": 2000,
                "student_loan": -10000,
            },
        )
        assert response.status_code == 201
        assert response.json["net_worth"] == -8000
        assert response.json["personal_wealth"] == -8000

    def test_only_liabilities(self, client):
        """Handles snapshot with only liabilities (no assets)."""
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "student_loan": -15000,
                "credit_cards": -2000,
            },
        )
        assert response.status_code == 201
        assert response.json["total_assets"] == 0
        assert response.json["total_liabilities"] == -17000
        assert response.json["net_worth"] == -17000
        # Percentages should be 0 when no assets
        assert response.json["stocks_pct"] == 0
        assert response.json["crypto_pct"] == 0
        assert response.json["cash_pct"] == 0

    def test_partial_update_preserves_other_fields(self, client):
        """PUT with partial data preserves other fields."""
        create_response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "cash": 5000,
                "savings": 10000,
                "crypto": 3000,
            },
        )
        snapshot_id = create_response.json["id"]

        # Update only cash
        response = client.put(f"/api/networth/{snapshot_id}", json={"cash": 8000})
        assert response.status_code == 200

        # Other fields should be preserved
        assert response.json["savings"] == 10000
        assert response.json["crypto"] == 3000
        # Cash should be updated
        assert response.json["cash"] == 8000
        # Net worth should be recalculated
        assert response.json["net_worth"] == 21000  # 8000 + 10000 + 3000

    def test_update_same_month_year_allowed(self, client):
        """PUT can update without changing month/year."""
        create_response = client.post(
            "/api/networth", json={"month": 1, "year": 2024, "cash": 1000}
        )
        snapshot_id = create_response.json["id"]

        # Update with same month/year explicitly
        response = client.put(
            f"/api/networth/{snapshot_id}",
            json={"month": 1, "year": 2024, "cash": 2000},
        )
        assert response.status_code == 200
        assert response.json["cash"] == 2000

    def test_boundary_month_values(self, client):
        """Month boundaries (1 and 12) work correctly."""
        response1 = client.post(
            "/api/networth", json={"month": 1, "year": 2024, "cash": 1000}
        )
        assert response1.status_code == 201
        assert response1.json["month"] == 1

        response12 = client.post(
            "/api/networth", json={"month": 12, "year": 2024, "cash": 2000}
        )
        assert response12.status_code == 201
        assert response12.json["month"] == 12

    def test_very_large_amounts(self, client):
        """Handles very large (but valid) amounts."""
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "house_worth": 999_999_999.99,
            },
        )
        assert response.status_code == 201
        assert response.json["house_worth"] == 999_999_999.99

    def test_change_from_previous_negative(self, client):
        """change_from_previous can be negative (wealth decreased)."""
        client.post("/api/networth", json={"month": 1, "year": 2024, "cash": 20000})

        response = client.post(
            "/api/networth", json={"month": 2, "year": 2024, "cash": 15000}
        )
        assert response.json["change_from_previous"] == -5000

    def test_percentage_rounding(self, client):
        """Percentage calculations handle rounding."""
        response = client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2024,
                "cash": 3333,
                "savings": 3333,
                "crypto": 3334,
            },
        )
        assert response.status_code == 201
        # Total = 10000, crypto = 3334
        # crypto_pct = 33.34%
        assert abs(response.json["crypto_pct"] - 33.34) < 0.01
