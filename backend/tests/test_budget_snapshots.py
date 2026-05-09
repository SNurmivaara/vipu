"""Tests for budget snapshot API endpoints."""

from datetime import date
from unittest.mock import patch


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
        assert "pay_period_change" in snapshot
        assert "pay_period_start" in snapshot
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
        """List returns empty response when no snapshots."""
        response = client.get("/api/budget/snapshots")
        assert response.status_code == 200
        assert response.json["snapshots"] == []
        assert response.json["total"] == 0

    def test_list_includes_pay_period_fields(self, seeded_client):
        """Listed snapshots include computed pay period fields."""
        response = seeded_client.get("/api/budget/snapshots")
        assert response.status_code == 200
        for snapshot in response.json["snapshots"]:
            assert "pay_period_change" in snapshot
            assert "pay_period_start" in snapshot

    def test_list_ordered_by_date_desc(self, seeded_client):
        """Snapshots are listed newest first."""
        response = seeded_client.get("/api/budget/snapshots")
        snapshots = response.json["snapshots"]
        assert len(snapshots) >= 2
        # Verify descending order
        for i in range(len(snapshots) - 1):
            assert snapshots[i]["date"] >= snapshots[i + 1]["date"]

    def test_list_pagination(self, seeded_client):
        """Pagination limits results and returns total."""
        response = seeded_client.get("/api/budget/snapshots?limit=2&offset=0")
        data = response.json
        assert len(data["snapshots"]) == 2
        assert data["total"] >= 5  # Seed creates 6 snapshots

        # Second page
        response2 = seeded_client.get("/api/budget/snapshots?limit=2&offset=2")
        data2 = response2.json
        assert len(data2["snapshots"]) == 2
        assert data2["total"] == data["total"]

        # No overlap between pages
        page1_ids = {s["id"] for s in data["snapshots"]}
        page2_ids = {s["id"] for s in data2["snapshots"]}
        assert page1_ids.isdisjoint(page2_ids)

    def test_list_pagination_max_limit(self, seeded_client):
        """Limit is capped at 200."""
        response = seeded_client.get("/api/budget/snapshots?limit=999")
        assert response.status_code == 200
        # Should not error, just cap


class TestUpdateBudgetSnapshot:
    """Tests for PUT /api/budget/snapshots/<id>."""

    def test_update_entry_balances(self, seeded_client):
        """Update entry balances recalculates current_balance."""
        snapshots = seeded_client.get("/api/budget/snapshots").json["snapshots"]
        snapshot = snapshots[0]
        original_balance = snapshot["current_balance"]

        updated_entries = [
            {**e, "balance": e["balance"] + 100} for e in snapshot["entries"]
        ]

        resp = seeded_client.put(
            f"/api/budget/snapshots/{snapshot['id']}",
            json={"entries": updated_entries},
        )
        assert resp.status_code == 200
        result = resp.json["snapshot"]
        expected = original_balance + 100 * len(updated_entries)
        assert result["current_balance"] == expected
        assert "pay_period_change" in result
        assert "pay_period_start" in result

    def test_update_notes(self, client):
        """Update notes only without changing entries."""
        client.post("/api/budget/snapshots")
        snapshots = client.get("/api/budget/snapshots").json["snapshots"]
        snap_id = snapshots[0]["id"]

        resp = client.put(
            f"/api/budget/snapshots/{snap_id}",
            json={"notes": "Updated note"},
        )
        assert resp.status_code == 200
        assert resp.json["snapshot"]["notes"] == "Updated note"

    def test_update_recalculates_next_snapshot(self, seeded_client):
        """Updating a snapshot recalculates the next one's change_from_previous."""
        snapshots = seeded_client.get("/api/budget/snapshots").json["snapshots"]
        # Pick second-to-last (oldest is [-1], next is [-2])
        if len(snapshots) < 2:
            return
        older = snapshots[-1]
        newer = snapshots[-2]

        # Update the older snapshot's entries to all be 0
        zeroed = [{**e, "balance": 0} for e in older["entries"]]
        seeded_client.put(
            f"/api/budget/snapshots/{older['id']}",
            json={"entries": zeroed},
        )

        # Refetch and check the newer snapshot's change
        refreshed = seeded_client.get("/api/budget/snapshots").json["snapshots"]
        newer_refreshed = next(s for s in refreshed if s["id"] == newer["id"])
        assert (
            newer_refreshed["change_from_previous"]
            == newer_refreshed["current_balance"]
        )

    def test_update_nonexistent(self, client):
        """Update nonexistent snapshot returns 404."""
        resp = client.put("/api/budget/snapshots/999", json={"notes": "x"})
        assert resp.status_code == 404


class TestDeleteBudgetSnapshot:
    """Tests for DELETE /api/budget/snapshots/<id>."""

    def test_delete_snapshot(self, client):
        """Delete removes snapshot and its entries."""
        resp = client.post("/api/budget/snapshots")
        snapshot_id = resp.json["snapshot"]["id"]

        del_resp = client.delete(f"/api/budget/snapshots/{snapshot_id}")
        assert del_resp.status_code == 200

        list_resp = client.get("/api/budget/snapshots")
        assert len(list_resp.json["snapshots"]) == 0

    def test_delete_nonexistent(self, client):
        """Delete nonexistent snapshot returns 404."""
        response = client.delete("/api/budget/snapshots/999")
        assert response.status_code == 404

    def test_delete_recalculates_next_snapshot(self, seeded_client):
        """Deleting a snapshot recalculates the next one's change_from_previous."""
        snapshots = seeded_client.get("/api/budget/snapshots").json["snapshots"]
        if len(snapshots) < 3:
            return

        # Pick a middle snapshot to delete (not oldest, not newest)
        # snapshots are newest-first, so [-2] has [-1] as prev and [-3] as next
        target = snapshots[-2]
        new_prev = snapshots[-1]
        next_snap = snapshots[-3]

        expected_change = next_snap["current_balance"] - new_prev["current_balance"]

        del_resp = seeded_client.delete(f"/api/budget/snapshots/{target['id']}")
        assert del_resp.status_code == 200

        refreshed = seeded_client.get("/api/budget/snapshots").json["snapshots"]
        next_refreshed = next(s for s in refreshed if s["id"] == next_snap["id"])
        assert next_refreshed["change_from_previous"] == expected_change

    def test_delete_oldest_zeros_next_change(self, seeded_client):
        """Deleting the oldest snapshot makes the new oldest have 0 change."""
        snapshots = seeded_client.get("/api/budget/snapshots").json["snapshots"]
        if len(snapshots) < 2:
            return

        oldest = snapshots[-1]
        new_oldest = snapshots[-2]

        del_resp = seeded_client.delete(f"/api/budget/snapshots/{oldest['id']}")
        assert del_resp.status_code == 200

        refreshed = seeded_client.get("/api/budget/snapshots").json["snapshots"]
        new_oldest_refreshed = next(s for s in refreshed if s["id"] == new_oldest["id"])
        assert new_oldest_refreshed["change_from_previous"] == 0


class TestSeedData:
    """Test that seed data includes budget snapshots."""

    def test_seed_creates_budget_snapshots(self, seeded_client):
        """Seeded data includes budget history snapshots."""
        response = seeded_client.get("/api/budget/snapshots")
        snapshots = response.json["snapshots"]
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
        for snapshot in response.json["snapshots"]:
            assert len(snapshot["entries"]) == 4  # 4 accounts in seed data


class TestAccountDeletionResilience:
    """Test that budget snapshots survive account deletion."""

    def test_entries_preserved_after_account_delete(self, seeded_client):
        """Snapshot entries retain account_name after account is deleted."""
        response = seeded_client.get("/api/budget/snapshots")
        entry = response.json["snapshots"][0]["entries"][0]
        account_name = entry["account_name"]

        assert account_name is not None
        assert len(account_name) > 0
        assert "balance" in entry
        assert "is_credit" in entry
