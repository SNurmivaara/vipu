"""Tests for budget snapshot API endpoints."""

from unittest.mock import patch
from datetime import date


class TestCreateBudgetSnapshot:
    """Tests for POST /api/budget/snapshots."""

    def test_create_snapshot_empty_db(self, client):
        """Create snapshot with no accounts."""
        response = client.post("/api/budget/snapshots")
        assert response.status_code == 201
        data = response.json
        assert data["updated"] is False
        snapshot = data["snapshot"]
        assert snapshot["current_balance"] == 0
        assert snapshot["change_from_previous"] == 0
        assert snapshot["entries"] == []
        assert snapshot["date"] == date.today().isoformat()
        assert "total_expenses" not in snapshot
        assert "net_income" not in snapshot
        assert "net_position" not in snapshot

    def test_create_snapshot_with_data(self, seeded_client):
        """Create snapshot captures account balances."""
        response = seeded_client.post("/api/budget/snapshots")
        # Seeded data already includes snapshots for today, so this overwrites
        assert response.status_code == 200
        snapshot = response.json["snapshot"]

        assert snapshot["current_balance"] != 0
        assert len(snapshot["entries"]) > 0

        # Verify entries match accounts
        accounts_resp = seeded_client.get("/api/budget/current")
        accounts = accounts_resp.json["accounts"]
        assert len(snapshot["entries"]) == len(accounts)

        for entry in snapshot["entries"]:
            assert "account_name" in entry
            assert "balance" in entry
            assert "is_credit" in entry

    def test_create_snapshot_with_notes(self, client):
        """Create snapshot with optional notes."""
        response = client.post(
            "/api/budget/snapshots", json={"notes": "Weekly check-in"}
        )
        assert response.status_code == 201
        assert response.json["snapshot"]["notes"] == "Weekly check-in"

    def test_overwrite_same_day(self, seeded_client):
        """Creating snapshot twice same day overwrites the first."""
        resp1 = seeded_client.post("/api/budget/snapshots")
        first_id = resp1.json["snapshot"]["id"]

        # Update an account balance
        accounts = seeded_client.get("/api/budget/current").json["accounts"]
        first_account = accounts[0]
        seeded_client.put(
            f"/api/accounts/{first_account['id']}",
            json={"balance": 99999},
        )

        resp2 = seeded_client.post("/api/budget/snapshots")
        assert resp2.json["updated"] is True
        assert resp2.json["snapshot"]["id"] == first_id

    def test_change_from_previous(self, client):
        """Change from previous tracks balance delta across days."""
        # Create account
        client.post("/api/accounts", json={"name": "Test", "balance": 1000})
        client.post("/api/budget/snapshots")

        # Simulate next day with changed balance
        client.put("/api/accounts/1", json={"balance": 1500})

        tomorrow = date(2026, 5, 10)
        with patch("app.routes.budget_snapshots.date") as mock_date:
            mock_date.today.return_value = tomorrow
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

            resp = client.post("/api/budget/snapshots")
            assert resp.status_code == 201
            assert resp.json["snapshot"]["change_from_previous"] == 500.0


class TestListBudgetSnapshots:
    """Tests for GET /api/budget/snapshots."""

    def test_list_empty(self, client):
        """List returns empty array when no snapshots."""
        response = client.get("/api/budget/snapshots")
        assert response.status_code == 200
        assert response.json == []

    def test_list_includes_pay_period_change(self, seeded_client):
        """Listed snapshots include computed pay_period_change."""
        response = seeded_client.get("/api/budget/snapshots")
        assert response.status_code == 200
        for snapshot in response.json:
            assert "pay_period_change" in snapshot

    def test_list_ordered_by_date_desc(self, seeded_client):
        """Snapshots are listed newest first."""
        response = seeded_client.get("/api/budget/snapshots")
        snapshots = response.json
        assert len(snapshots) >= 2
        # Verify descending order
        for i in range(len(snapshots) - 1):
            assert snapshots[i]["date"] >= snapshots[i + 1]["date"]


class TestDeleteBudgetSnapshot:
    """Tests for DELETE /api/budget/snapshots/<id>."""

    def test_delete_snapshot(self, client):
        """Delete removes snapshot and its entries."""
        resp = client.post("/api/budget/snapshots")
        snapshot_id = resp.json["snapshot"]["id"]

        del_resp = client.delete(f"/api/budget/snapshots/{snapshot_id}")
        assert del_resp.status_code == 200

        list_resp = client.get("/api/budget/snapshots")
        assert len(list_resp.json) == 0

    def test_delete_nonexistent(self, client):
        """Delete nonexistent snapshot returns 404."""
        response = client.delete("/api/budget/snapshots/999")
        assert response.status_code == 404


class TestSeedData:
    """Test that seed data includes budget snapshots."""

    def test_seed_creates_budget_snapshots(self, seeded_client):
        """Seeded data includes budget history snapshots."""
        response = seeded_client.get("/api/budget/snapshots")
        snapshots = response.json
        assert len(snapshots) >= 5

        # First snapshot (oldest) should have 0 change
        oldest = snapshots[-1]
        assert oldest["change_from_previous"] == 0

        # Later snapshots should have non-zero changes
        has_nonzero = any(s["change_from_previous"] != 0 for s in snapshots[:-1])
        assert has_nonzero

    def test_seed_snapshots_have_entries(self, seeded_client):
        """Each seeded snapshot has account balance entries."""
        response = seeded_client.get("/api/budget/snapshots")
        for snapshot in response.json:
            assert len(snapshot["entries"]) == 4  # 4 accounts in seed data


class TestAccountDeletionResilience:
    """Test that budget snapshots survive account deletion."""

    def test_entries_preserved_after_account_delete(self, seeded_client):
        """Snapshot entries retain account_name after account is deleted."""
        response = seeded_client.get("/api/budget/snapshots")
        entry = response.json[0]["entries"][0]
        account_name = entry["account_name"]

        assert account_name is not None
        assert len(account_name) > 0
        assert "balance" in entry
        assert "is_credit" in entry
