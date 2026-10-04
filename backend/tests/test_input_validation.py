"""Hostile and malformed input gets a 400, never a 500 or a stored value."""

import json

import pytest

from app.config import Config
from app.validation import MAX_FREQUENCY_VALUE

# JSON accepts these spellings through Python's parser, and Decimal accepts
# the strings, so both forms must be refused.
NON_FINITE_LITERALS = ["NaN", "Infinity", "-Infinity"]
NON_FINITE_STRINGS = ['"NaN"', '"sNaN"', '"Infinity"', '"-inf"']
NON_FINITE = NON_FINITE_LITERALS + NON_FINITE_STRINGS


def send(client, method: str, url: str, body: str):
    """Send a raw JSON body, so NaN and Infinity literals reach the API."""
    return getattr(client, method)(
        url, data=body, headers={"Content-Type": "application/json"}
    )


def assert_400(response) -> str:
    assert response.status_code == 400, response.get_data(as_text=True)
    error = response.get_json()["error"]
    assert isinstance(error, str)
    return error


# ---------------------------------------------------------------------------
# Non-finite numbers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("number", NON_FINITE)
class TestNonFiniteNumbers:
    def test_account_balance(self, client, number):
        url = "/api/accounts"
        assert_400(send(client, "post", url, f'{{"name": "A", "balance": {number}}}'))
        account = client.post(url, json={"name": "A", "balance": 10}).get_json()
        body = f'{{"balance": {number}}}'
        assert_400(send(client, "put", f"{url}/{account['id']}", body))
        assert client.get(url).get_json()[0]["balance"] == 10.0

    def test_expense_amount(self, client, number):
        url = "/api/expenses"
        assert_400(send(client, "post", url, f'{{"name": "E", "amount": {number}}}'))
        item = client.post(url, json={"name": "E", "amount": 5}).get_json()
        body = f'{{"amount": {number}}}'
        assert_400(send(client, "put", f"{url}/{item['id']}", body))

    def test_income_amount_and_tax(self, client, number):
        url = "/api/income"
        body = f'{{"name": "I", "gross_amount": {number}}}'
        assert_400(send(client, "post", url, body))
        body = f'{{"name": "I", "gross_amount": 100, "tax_percentage": {number}}}'
        assert_400(send(client, "post", url, body))
        item = client.post(url, json={"name": "I", "gross_amount": 100}).get_json()
        for field in ("gross_amount", "tax_percentage"):
            body = f'{{"{field}": {number}}}'
            assert_400(send(client, "put", f"{url}/{item['id']}", body))

    def test_budget_settings(self, client, number):
        body = f'{{"tax_percentage": {number}}}'
        assert_400(send(client, "put", "/api/settings", body))
        assert client.get("/api/settings").get_json()["tax_percentage"] == 25.0

    def test_goal_amounts(self, client, number):
        url = "/api/goals"
        base = '"name": "G", "goal_type": "net_worth"'
        assert_400(send(client, "post", url, f'{{{base}, "target_value": {number}}}'))
        body = f'{{{base}, "target_value": 10, "current_amount": {number}}}'
        assert_400(send(client, "post", url, body))
        goal = client.post(
            url, json={"name": "G", "goal_type": "net_worth", "target_value": 10}
        ).get_json()
        body = f'{{"target_value": {number}}}'
        assert_400(send(client, "put", f"{url}/{goal['id']}", body))

    def test_networth_entry(self, client, number):
        client.post("/api/networth/categories/seed")
        category_id = client.get("/api/networth/categories").get_json()[0]["id"]
        entries = f'[{{"category_id": {category_id}, "amount": {number}}}]'
        body = f'{{"month": 1, "year": 2024, "entries": {entries}}}'
        assert_400(send(client, "post", "/api/networth", body))

    def test_budget_snapshot_entry(self, client, number):
        snapshot = client.post("/api/budget/snapshots", json={}).get_json()["snapshot"]
        body = f'{{"entries": [{{"account_name": "A", "balance": {number}}}]}}'
        url = f"/api/budget/snapshots/{snapshot['id']}"
        assert_400(send(client, "put", url, body))


@pytest.mark.parametrize("number", NON_FINITE_LITERALS)
def test_fire_calculation_rejects_non_finite(client, number):
    body = json.dumps(
        {
            "current_net_worth": 0,
            "monthly_contribution": 1,
            "annual_expenses": 1,
            "annual_return_pct": 5,
            "inflation_pct": 2,
            "current_age": 30,
            "target_retirement_age": 60,
            "safe_withdrawal_rate": 4,
        }
    ).replace('"current_net_worth": 0', f'"current_net_worth": {number}')
    assert send(client, "post", "/api/forecasting/calculate", body).status_code == 400


@pytest.mark.parametrize("number", NON_FINITE_LITERALS)
@pytest.mark.parametrize(
    "body",
    [
        '{{"inflation_pct": {n}}}',
        '{{"current_age": {n}}}',
        '{{"monthly_savings_override": {n}}}',
        '{{"group_return_rates": {{"Stocks": {n}}}}}',
        '{{"liability_terms": {{"Loan": {{"rate_pct": {n}}}}}}}',
        '{{"liability_terms": {{"Loan": {{"monthly_payment": {n}}}}}}}',
    ],
)
def test_forecasting_settings_reject_non_finite(client, body, number):
    before = client.get("/api/forecasting/settings").get_json()
    assert_400(send(client, "put", "/api/forecasting/settings", body.format(n=number)))
    after = client.get("/api/forecasting/settings").get_json()
    assert {k: v for k, v in after.items() if k != "updated_at"} == {
        k: v for k, v in before.items() if k != "updated_at"
    }


def test_forecasting_settings_cap_money_fields(client):
    url = "/api/forecasting/settings"
    error = assert_400(client.put(url, json={"monthly_savings_override": 1e300}))
    assert "exceeds maximum" in error
    terms = {"Loan": {"rate_pct": 3, "monthly_payment": 1e300}}
    assert_400(client.put(url, json={"liability_terms": terms}))
    ok = client.put(url, json={"monthly_savings_override": 1500.5})
    assert ok.get_json()["monthly_savings_override"] == 1500.5


def test_fire_calculation_caps_money_inputs(client):
    body = {
        "current_net_worth": 1e308,
        "monthly_contribution": 1,
        "annual_expenses": 1,
        "annual_return_pct": 5,
        "inflation_pct": 2,
        "current_age": 30,
        "target_retirement_age": 60,
        "safe_withdrawal_rate": 4,
    }
    assert client.post("/api/forecasting/calculate", json=body).status_code == 400
    body["current_net_worth"] = 1e9
    assert client.post("/api/forecasting/calculate", json=body).status_code == 200


def test_unparseable_numbers_are_rejected(client):
    error = assert_400(client.post("/api/accounts", json={"name": "A", "balance": "x"}))
    assert error == "balance must be a number"
    body = {"name": "A", "balance": 1, "payment_due_day": "x"}
    assert_400(client.post("/api/accounts", json=body))
    assert_400(client.post("/api/expenses", json={"name": "E", "amount": True}))
    body = {"name": "E", "amount": 1, "due_day": "first"}
    assert_400(client.post("/api/expenses", json=body))


def test_valid_numbers_keep_their_contract(client):
    """Numeric strings still parse and amounts still serialise as floats."""
    account = client.post("/api/accounts", json={"name": "A", "balance": "-12.50"})
    assert account.status_code == 201
    assert account.get_json()["balance"] == -12.5
    income = client.post(
        "/api/income", json={"name": "I", "gross_amount": 3000, "tax_percentage": 20}
    )
    assert income.status_code == 201
    assert income.get_json()["tax_percentage"] == 20.0


def test_duplicate_networth_entry_category_is_rejected(client):
    client.post("/api/networth/categories/seed")
    category_id = client.get("/api/networth/categories").get_json()[0]["id"]
    entries = [
        {"category_id": category_id, "amount": 1},
        {"category_id": category_id, "amount": 2},
    ]
    response = client.post(
        "/api/networth", json={"month": 1, "year": 2024, "entries": entries}
    )
    assert_400(response)


# ---------------------------------------------------------------------------
# Budget snapshot pagination and entries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query",
    ["limit=-1", "limit=abc", "limit=1.5", "offset=-5", "offset=x", "offset=1e3"],
)
def test_snapshot_pagination_rejects_bad_values(client, query):
    assert_400(client.get(f"/api/budget/snapshots?{query}"))


def test_snapshot_pagination_accepts_and_clamps(client):
    client.post("/api/budget/snapshots", json={})
    response = client.get("/api/budget/snapshots?limit=500&offset=0")
    assert response.status_code == 200
    assert response.get_json()["total"] == 1
    assert len(response.get_json()["snapshots"]) == 1
    response = client.get("/api/budget/snapshots?limit=0")
    assert response.status_code == 200
    assert response.get_json()["snapshots"] == []


def test_snapshot_update_validates_before_replacing(client):
    client.post("/api/accounts", json={"name": "Cash", "balance": 100})
    snapshot = client.post("/api/budget/snapshots", json={}).get_json()["snapshot"]
    url = f"/api/budget/snapshots/{snapshot['id']}"
    bad_entries = [
        {"account_name": "Cash", "balance": 50},
        {"account_name": "Other", "balance": 2e9},
    ]
    assert_400(client.put(url, json={"entries": bad_entries}))
    assert_400(client.put(url, json={"entries": ["not an object"]}))
    assert_400(
        client.put(url, json={"entries": [{"account_name": "X", "account_id": 999}]})
    )
    after = client.get("/api/budget/snapshots").get_json()["snapshots"][0]
    assert after["current_balance"] == 100.0
    assert [e["balance"] for e in after["entries"]] == [100.0]


# ---------------------------------------------------------------------------
# frequency_value bounds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url, amount_field", [("/api/expenses", "amount"), ("/api/income", "gross_amount")]
)
class TestFrequencyValueBounds:
    def test_create(self, client, url, amount_field):
        def create(value):
            body = {"name": "X", amount_field: 10, "frequency_value": value}
            return client.post(url, json=body)

        assert create(MAX_FREQUENCY_VALUE).status_code == 201
        for value in (0, MAX_FREQUENCY_VALUE + 1, 10**12, "many"):
            assert_400(create(value))
        error = assert_400(create(2**40))
        assert error == f"frequency_value must be between 1 and {MAX_FREQUENCY_VALUE}"

    def test_update(self, client, url, amount_field):
        item = client.post(url, json={"name": "X", amount_field: 10}).get_json()
        item_url = f"{url}/{item['id']}"
        assert_400(client.put(item_url, json={"frequency_value": 10**6}))
        ok = client.put(
            item_url, json={"frequency_value": 12, "frequency_unit": "years"}
        )
        assert ok.status_code == 200
        assert ok.get_json()["frequency_value"] == 12

    def test_largest_value_keeps_budget_working(self, client, url, amount_field):
        for unit in ("days", "weeks", "months", "years"):
            body = {
                "name": unit,
                amount_field: 10,
                "frequency_value": MAX_FREQUENCY_VALUE,
                "frequency_unit": unit,
            }
            assert client.post(url, json=body).status_code == 201
        assert client.get("/api/budget/current").status_code == 200
        assert client.get("/api/goals/roadmap").status_code == 200


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


def seed_everything(client) -> None:
    """Budget, net worth and goals through the normal routes."""
    client.post("/api/seed")
    client.post("/api/networth/categories/seed")
    client.post("/api/networth/seed")
    categories = client.get("/api/networth/categories").get_json()
    client.post(
        "/api/goals",
        json={"name": "Net worth 1M", "goal_type": "net_worth", "target_value": 1e6},
    )
    client.post(
        "/api/goals",
        json={
            "name": "Buffer",
            "goal_type": "savings_goal",
            "target_value": 5000,
            "current_amount": 1200.5,
            "category_id": categories[0]["id"],
            "target_date": "2030-06-01T00:00:00+00:00",
        },
    )
    client.post(
        "/api/goals",
        json={"name": "Card", "goal_type": "debt_payoff", "target_value": 900},
    )


def test_export_round_trips_through_import(client):
    seed_everything(client)
    exported = client.get("/api/export").get_json()
    assert exported["networth_snapshots"] and exported["goals"]

    response = client.post("/api/import", json=exported)
    assert response.status_code == 200, response.get_json()
    counts = response.get_json()["counts"]
    assert counts["networth_snapshots"] == len(exported["networth_snapshots"])
    assert counts["goals"] == len(exported["goals"])

    assert client.get("/api/export").get_json() == exported


def test_version_1_import_round_trips(client):
    client.post("/api/seed")
    exported = client.get("/api/export").get_json()
    budget = {k: exported[k] for k in ("settings", "accounts", "income", "expenses")}
    response = client.post("/api/import", json={"version": 1, **budget})
    assert response.status_code == 200
    reexported = client.get("/api/export").get_json()
    assert {k: reexported[k] for k in budget} == budget


def _mutations():
    """(description, change) pairs that each make a valid export invalid."""

    def set_path(*path, value):
        def change(data):
            target = data
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value

        return change

    return [
        ("long account name", set_path("accounts", 0, "name", value="x" * 101)),
        ("blank account name", set_path("accounts", 0, "name", value="   ")),
        ("NaN balance", set_path("accounts", 0, "balance", value="NaN")),
        ("huge balance", set_path("accounts", 0, "balance", value=1e12)),
        ("infinite income", set_path("income", 0, "gross_amount", value="Infinity")),
        ("tax over 100", set_path("income", 0, "tax_percentage", value=150)),
        ("settings tax NaN", set_path("settings", "tax_percentage", value="sNaN")),
        ("missing expense amount", lambda d: d["expenses"][0].pop("amount")),
        ("bad group type", set_path("networth_groups", 0, "group_type", value="x")),
        ("bad color", set_path("networth_groups", 0, "color", value="red")),
        (
            "huge display order",
            set_path("networth_categories", 0, "display_order", value=2**40),
        ),
        ("bad month", set_path("networth_snapshots", 0, "month", value=13)),
        (
            "NaN entry",
            set_path("networth_snapshots", 0, "entries", 0, "amount", value="NaN"),
        ),
        (
            "duplicate snapshot",
            lambda d: d["networth_snapshots"].append(d["networth_snapshots"][0]),
        ),
        (
            "duplicate entry",
            lambda d: d["networth_snapshots"][0]["entries"].append(
                d["networth_snapshots"][0]["entries"][0]
            ),
        ),
        ("negative target", set_path("goals", 0, "target_value", value=-1)),
        ("bad goal type", set_path("goals", 0, "goal_type", value="dream")),
        ("bad goal date", set_path("goals", 0, "target_date", value="soon")),
        ("accounts not a list", set_path("accounts", value={"name": "A"})),
        (
            "entry not an object",
            set_path("networth_snapshots", 0, "entries", value=[1]),
        ),
    ]


@pytest.mark.parametrize("description, change", _mutations())
def test_invalid_import_changes_nothing(client, description, change):
    seed_everything(client)
    exported = client.get("/api/export").get_json()

    invalid = json.loads(json.dumps(exported))
    # Rename the expenses so a partial write would show in the export.
    for expense in invalid["expenses"]:
        expense["name"] = "Imported " + expense["name"][:80]
    change(invalid)

    response = client.post("/api/import", json=invalid)
    assert_400(response)
    assert client.get("/api/export").get_json() == exported


def test_invalid_import_error_names_the_field(client):
    data = {"version": 2, "accounts": [{"name": "A", "balance": 1}]}
    data["networth_snapshots"] = [{"month": 1, "year": 2024, "entries": []}] * 2
    error = assert_400(client.post("/api/import", json=data))
    assert error.startswith("networth_snapshots[1]")
    error = assert_400(
        client.post("/api/import", json={"accounts": [{"name": "A", "balance": 2e9}]})
    )
    assert error == "accounts[0].balance exceeds maximum allowed value"


def test_import_rejects_non_object_body(client):
    assert_400(client.post("/api/import", json=[{"version": 2}]))
    assert_400(client.post("/api/import", json={"version": True}))


# ---------------------------------------------------------------------------
# Request size
# ---------------------------------------------------------------------------


def test_max_content_length_fits_a_large_export():
    assert Config.MAX_CONTENT_LENGTH == 5 * 1024 * 1024


def test_oversize_request_gets_413(client):
    body = json.dumps({"version": 2, "padding": "x" * Config.MAX_CONTENT_LENGTH})
    response = send(client, "post", "/api/import", body)
    assert response.status_code == 413
    assert response.is_json


def test_large_realistic_import_is_accepted(client):
    """A century of monthly snapshots for every seeded category fits the cap."""
    client.post("/api/networth/categories/seed")
    exported = client.get("/api/export").get_json()
    entries = [
        {"category_name": c["name"], "amount": -1234567.89}
        for c in exported["networth_categories"]
    ]
    exported["networth_snapshots"] = [
        {"month": month, "year": year, "entries": entries}
        for year in range(1950, 2050)
        for month in range(1, 13)
    ]
    body = json.dumps(exported)
    assert len(body) < Config.MAX_CONTENT_LENGTH
    response = send(client, "post", "/api/import", body)
    assert response.status_code == 200, response.get_json()
