import os
import tempfile
import pytest
import app as app_module
from database import get_db_connection, create_default_categories


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr("database.DB_NAME", db_file)

    conn = get_db_connection()
    with open("schema.sql") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as client:
        yield client


def register_and_login(client):
    client.post("/register", data={"email": "u@test.com", "password": "password123"})
    client.post("/login", data={"email": "u@test.com", "password": "password123"})


def get_food_category_id():
    conn = get_db_connection()
    row = conn.execute("SELECT category_id FROM categories WHERE name = 'Food'").fetchone()
    conn.close()
    return row["category_id"]


def test_adding_transaction_through_route_creates_near_limit_alert(client):
    register_and_login(client)
    food_id = get_food_category_id()

    client.post("/budgets/create", data={
        "category_id": food_id, "monthly_limit": "100", "month": "2026-07"
    })

    client.post("/transactions", data={
        "amount": "80", "type": "expense", "category_id": food_id,
        "transaction_date": "2026-07-15", "description": "groceries"
    })

    conn = get_db_connection()
    alert = conn.execute("SELECT alert_type FROM alerts ORDER BY alert_id DESC LIMIT 1").fetchone()
    conn.close()
    assert alert is not None
    assert alert["alert_type"] == "near limit"


def test_adding_transaction_through_route_creates_over_limit_alert(client):
    register_and_login(client)
    food_id = get_food_category_id()

    client.post("/budgets/create", data={
        "category_id": food_id, "monthly_limit": "100", "month": "2026-07"
    })
    client.post("/transactions", data={
        "amount": "100", "type": "expense", "category_id": food_id,
        "transaction_date": "2026-07-15", "description": "rent"
    })

    conn = get_db_connection()
    alert = conn.execute("SELECT alert_type FROM alerts ORDER BY alert_id DESC LIMIT 1").fetchone()
    conn.close()
    assert alert is not None
    assert alert["alert_type"] == "over limit"


def test_transaction_below_threshold_creates_no_alert(client):
    register_and_login(client)
    food_id = get_food_category_id()

    client.post("/budgets/create", data={
        "category_id": food_id, "monthly_limit": "100", "month": "2026-07"
    })
    client.post("/transactions", data={
        "amount": "50", "type": "expense", "category_id": food_id,
        "transaction_date": "2026-07-15", "description": "snacks"
    })

    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(*) AS c FROM alerts").fetchone()["c"]
    conn.close()
    assert count == 0


def test_invalid_budget_month_is_rejected(client):
    register_and_login(client)
    food_id = get_food_category_id()

    client.post("/budgets/create", data={
        "category_id": food_id, "monthly_limit": "100", "month": "2026-13"
    })

    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(*) AS c FROM budgets").fetchone()["c"]
    conn.close()
    assert count == 0


def test_non_finite_budget_limit_is_rejected(client):
    register_and_login(client)
    food_id = get_food_category_id()

    client.post("/budgets/create", data={
        "category_id": food_id, "monthly_limit": "nan", "month": "2026-07"
    })

    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(*) AS c FROM budgets").fetchone()["c"]
    conn.close()
    assert count == 0
