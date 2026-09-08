"""Tests for the AI summary digest and GET /api/summary."""

import datetime

import pytest


def freeze(monkeypatch, year, month, day):
    """Freeze today across every module that reads the clock.

    Each module calls date.today() through its own imported name, so a new call
    site needs a new patch target. summary.py is one: it reads the clock in the
    route handler and passes it down.
    """
    from app.routes import budget as budget_route
    from app.routes import expenses as expenses_route
    from app.routes import goals as goals_route
    from app.routes import income as income_route
    from app.routes import summary as summary_route

    class _FixedDate(datetime.date):
        @classmethod
        def today(cls):
            return cls(year, month, day)

    for module in (
        summary_route,
        budget_route,
        goals_route,
        expenses_route,
        income_route,
    ):
        monkeypatch.setattr(module, "date", _FixedDate)


@pytest.fixture
def digest(seeded_client, monkeypatch):
    """The digest for the seeded fixture, with today frozen to 2026-06-10."""
    freeze(monkeypatch, 2026, 6, 10)
    response = seeded_client.get("/api/summary")
    assert response.status_code == 200
    return response.json


class TestEndpoint:
    """Shape of the GET /api/summary response."""

    def test_returns_versioned_envelope(self, digest):
        """The response carries the format version and the date it was built."""
        assert digest["format_version"] == "vipu-export/v1"
        assert digest["generated_at"] == "2026-06-10"
        assert digest["markdown"].startswith(
            "# Vipu financial snapshot (2026-06-10)\n\nFormat: vipu-export/v1."
        )

    def test_works_with_an_empty_database(self, client, monkeypatch):
        """No accounts, no goals and no snapshots is a valid state, not a 500."""
        freeze(monkeypatch, 2026, 6, 10)
        response = client.get("/api/summary")
        assert response.status_code == 200
        markdown = response.json["markdown"]
        assert "- Wealth section: no net worth snapshots recorded yet." in markdown
        assert "No net worth snapshots recorded yet." in markdown
        assert "### Accounts (live)\n- (none)" in markdown

    def test_sections_appear_in_order(self, digest):
        """Section order is part of the format: As of, Budget, Wealth, FIRE."""
        markdown = digest["markdown"]
        headings = [
            "## As of",
            "## Budget",
            "### Current position",
            "### Monthly rates",
            "### Income (gross -> net per occurrence)",
            "### Accounts (live)",
            "### Expenses",
            "### Financial roadmap",
            "## Wealth",
            "## FIRE projection",
        ]
        positions = [markdown.index(heading) for heading in headings]
        assert positions == sorted(positions)


class TestCaveats:
    """The prose a model would otherwise get wrong.

    These sentences are the reason the document works. Assert them verbatim so
    a well-meaning rewrite has to be deliberate.
    """

    def test_card_is_charged_once(self, digest):
        assert (
            "- A card balance is charged once, on its first due day from today, "
            "not in every period." in digest["markdown"]
        )

    def test_budget_and_wealth_date_skew(self, seeded_client, monkeypatch):
        freeze(monkeypatch, 2026, 6, 10)
        seeded_client.post("/api/networth/categories/seed")
        seeded_client.post("/api/networth/seed")
        markdown = seeded_client.get("/api/summary").json["markdown"]
        assert "Monthly cadence, so it can lag the budget section by weeks." in markdown
        assert (
            "- The same account may therefore show different figures in the two "
            "sections. Both are correct as of their own date; prefer the budget "
            "section for current cash." in markdown
        )

    def test_settled_occurrences_are_labelled(self, digest):
        """A settled row stays on the list, marked as excluded from the total."""
        assert "(already paid, not counted above)" in digest["markdown"]

    def test_monthly_rates_exclude_one_time_items(self, digest):
        markdown = digest["markdown"]
        assert (
            "Recurring items normalized to a per-month rate (a quarterly bill "
            "counts as a third, a yearly one as a twelfth). One-time items are "
            "excluded here and listed separately below." in markdown
        )
        assert "One-time (excluded from the monthly rates above):" in markdown

    def test_linear_goal_math_versus_compounding_fire(self, seeded_client, monkeypatch):
        """Stated only when there is a net worth goal to state it about."""
        freeze(monkeypatch, 2026, 6, 10)
        seeded_client.post("/api/networth/categories/seed")
        seeded_client.post("/api/networth/seed")
        seeded_client.post(
            "/api/goals",
            json={
                "name": "Half a million",
                "goal_type": "net_worth",
                "target_value": 500000,
            },
        )
        markdown = seeded_client.get("/api/summary").json["markdown"]
        assert (
            "Progress and required-monthly figures below are zero-growth linear: "
            "they assume no investment return. The FIRE section compounds "
            "instead, so the two can disagree about whether a target is "
            "reachable." in markdown
        )


class TestFigures:
    """The digest reports the same numbers the endpoints it composes do."""

    def test_current_position_matches_the_budget_endpoint(
        self, seeded_client, monkeypatch
    ):
        freeze(monkeypatch, 2026, 6, 10)
        totals = seeded_client.get("/api/budget/current").json["totals"]
        markdown = seeded_client.get("/api/summary").json["markdown"]

        assert (
            f"- Cash across all non-credit accounts: {totals['cash_balance']:.2f} €"
            in markdown
        )
        assert f"- Next payday: {totals['next_payday']}" in markdown
        low = totals["cash_low_point"]
        assert f"{low['balance']:.2f} € on {low['date']}" in markdown

    def test_seeded_monthly_rates(self, digest):
        """The seeded fixture's monthly rates, as the budget endpoint derives."""
        markdown = digest["markdown"]
        assert "- Net income: 4155.84 €/mo" in markdown
        assert "- Expenses: 2210.19 €/mo" in markdown
        assert "- Surplus: 1945.65 €/mo" in markdown

    def test_income_lines_show_gross_and_net(self, digest):
        """Default-taxed, untaxed and deduction lines each read differently."""
        markdown = digest["markdown"]
        assert (
            "- Salary: 5000.00 € -> 3750.00 € (taxed at default 25%; monthly, "
            "lands on day 25)" in markdown
        )
        assert (
            "- Dividends: 200.00 € -> 200.00 € (untaxed; every 3 months, lands "
            "on day 1)" in markdown
        )
        assert (
            "- Lunch benefit: -150.00 € (deduction of 75% of 200.00 €, subtracted "
            "from net pay after tax; monthly, lands on day 25)" in markdown
        )

    def test_credit_cards_carry_their_due_day(self, digest):
        assert "Credit cards (negative balance = amount owed):" in digest["markdown"]
        assert "payment due day" in digest["markdown"]

    def test_roadmap_steps_are_numbered_in_plan_order(self, digest):
        markdown = digest["markdown"]
        assert "1. Pay off Visa (pay off debt):" in markdown
        assert "2. Emergency fund (save up):" in markdown
        assert "3. Travel fund (save up):" in markdown

    def test_wealth_matches_the_latest_snapshot(self, seeded_client, monkeypatch):
        freeze(monkeypatch, 2026, 6, 10)
        seeded_client.post("/api/networth/categories/seed")
        seeded_client.post("/api/networth/seed")
        latest = seeded_client.get("/api/networth").json[0]
        markdown = seeded_client.get("/api/summary").json["markdown"]

        label = f"{latest['year']}-{latest['month']:02d}"
        assert f"### Net worth ({label} snapshot)" in markdown
        assert f"- Net worth: {latest['net_worth']:.2f} €" in markdown
        assert (
            f"- Assets: {latest['total_assets']:.2f} €, liabilities: "
            f"{latest['total_liabilities']:.2f} €" in markdown
        )
        assert "### Trend (newest first)" in markdown

    def test_fire_inputs_are_labelled_as_derived_or_overridden(
        self, seeded_client, monkeypatch
    ):
        """Which figure is a manual override is the whole point of the label."""
        freeze(monkeypatch, 2026, 6, 10)
        markdown = seeded_client.get("/api/summary").json["markdown"]
        assert "(the budget's monthly surplus)" in markdown
        assert "(monthly expenses x 12)" in markdown

        seeded_client.put(
            "/api/forecasting/settings",
            json={"monthly_savings_override": 2200, "annual_expenses_override": 31000},
        )
        markdown = seeded_client.get("/api/summary").json["markdown"]
        assert (
            "- Monthly savings input: 2200.00 €/mo (manual override; the budget's "
            "own surplus is 1945.65 €/mo)" in markdown
        )
        assert "- Annual expenses input: 31000.00 €/yr (manual override)" in markdown


class TestOccurrenceOverrides:
    """One-off timing corrections are why a period can disagree with a schedule."""

    def test_a_settled_occurrence_is_annotated(self, seeded_client, monkeypatch):
        freeze(monkeypatch, 2026, 6, 10)
        rows = seeded_client.get("/api/budget/current").json
        row = next(
            r
            for r in rows["totals"]["expenses_before_payday_list"]
            if r["can_settle"] and not r["is_settled"]
        )
        seeded_client.put(
            f"/api/expenses/{row['id']}/occurrence",
            json={"occurrence_date": row["next_occurrence_date"], "settled": True},
        )
        markdown = seeded_client.get("/api/summary").json["markdown"]
        assert (
            f"[{row['next_occurrence_date']} occurrence already settled ahead of "
            "its day, so it is in the balance and excluded from the period "
            "figures]" in markdown
        )

    def test_a_pending_occurrence_is_annotated(self, seeded_client, monkeypatch):
        freeze(monkeypatch, 2026, 6, 10)
        rows = seeded_client.get("/api/budget/current").json
        row = next(
            r
            for r in rows["totals"]["expenses_before_payday_list"]
            if r["can_settle"] and r["is_settled"]
        )
        seeded_client.put(
            f"/api/expenses/{row['id']}/occurrence",
            json={"occurrence_date": row["next_occurrence_date"], "settled": False},
        )
        markdown = seeded_client.get("/api/summary").json["markdown"]
        assert (
            f"[{row['next_occurrence_date']} occurrence has not moved yet despite "
            "its day passing, so it still counts in the period figures]" in markdown
        )


class TestShortfall:
    """A plan that starts behind says so, in both the budget and roadmap halves."""

    def test_negative_low_point_explains_itself(self, seeded_client, monkeypatch):
        freeze(monkeypatch, 2026, 6, 10)
        for account in seeded_client.get("/api/budget/current").json["accounts"]:
            if not account["is_credit"]:
                seeded_client.put(
                    f"/api/accounts/{account['id']}", json={"balance": -100}
                )
        markdown = seeded_client.get("/api/summary").json["markdown"]
        assert (
            ". The account goes under before the pay that covers those bills "
            "arrives, so the projections below are reached through a shortfall "
            "rather than around it." in markdown
        )
        assert "The plan starts " in markdown
        assert "months of surplus, cleared before any goal progresses." in markdown
