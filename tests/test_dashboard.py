from datetime import datetime

import pytest

import app as app_module
from database import get_db_connection


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_file = str(tmp_path / "dashboard_test.db")
    monkeypatch.setattr("database.DB_NAME", db_file)

    conn = get_db_connection()
    with open("schema.sql", encoding="utf-8") as schema_file:
        conn.executescript(schema_file.read())
    conn.commit()
    conn.close()

    app_module.app.config["TESTING"] = True

    with app_module.app.test_client() as test_client:
        yield test_client


def register_and_login(client, email="dashboard@test.com"):
    client.post(
        "/register",
        data={"email": email, "password": "password123"},
    )
    client.post(
        "/login",
        data={"email": email, "password": "password123"},
    )


def get_user_and_food_category():
    conn = get_db_connection()
    user = conn.execute(
        "SELECT user_id FROM users WHERE email = ?",
        ("dashboard@test.com",),
    ).fetchone()
    category = conn.execute(
        """
        SELECT category_id
        FROM categories
        WHERE user_id = ? AND name = 'Food'
        """,
        (user["user_id"],),
    ).fetchone()
    conn.close()
    return user["user_id"], category["category_id"]


def test_dashboard_requires_login(client):
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_empty_dashboard_shows_zero_values_and_empty_messages(client):
    register_and_login(client)

    response = client.get("/dashboard")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Total Income" in page
    assert "Total Expenses" in page
    assert "Remaining Budget" in page
    assert "No alerts yet." in page
    assert "No recent transactions available." in page
    assert 'href="/transactions">Add Transaction</a>' in page
    assert page.count("$0.00") >= 3


def test_dashboard_totals_and_remaining_budget_are_user_scoped(client):
    register_and_login(client)
    user_id, category_id = get_user_and_food_category()
    now = datetime.now()
    month = now.strftime("%Y-%m")
    transaction_date = f"{month}-15"
    if now.month == 1:
        previous_month = f"{now.year - 1}-12"
    else:
        previous_month = f"{now.year}-{now.month - 1:02d}"
    previous_transaction_date = f"{previous_month}-15"

    conn = get_db_connection()

    conn.execute(
        """
        INSERT INTO budgets (user_id, category_id, monthly_limit, month)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, category_id, 500.00, month),
    )

    conn.execute(
        """
        INSERT INTO transactions
            (user_id, category_id, amount, type, description, transaction_date)
        VALUES (?, ?, ?, 'income', ?, ?)
        """,
        (user_id, category_id, 1000.00, "Paycheck", transaction_date),
    )
    conn.execute(
        """
        INSERT INTO transactions
            (user_id, category_id, amount, type, description, transaction_date)
        VALUES (?, ?, ?, 'expense', ?, ?)
        """,
        (user_id, category_id, 200.00, "Groceries", transaction_date),
    )

    # Previous-month transactions must not be included in dashboard totals.
    conn.execute(
        """
        INSERT INTO transactions
            (user_id, category_id, amount, type, description, transaction_date)
        VALUES (?, ?, ?, 'income', ?, ?)
        """,
        (user_id, category_id, 1234.56, "Previous month income", previous_transaction_date),
    )
    conn.execute(
        """
        INSERT INTO transactions
            (user_id, category_id, amount, type, description, transaction_date)
        VALUES (?, ?, ?, 'expense', ?, ?)
        """,
        (user_id, category_id, 432.10, "Previous month expense", previous_transaction_date),
    )

    other_user = conn.execute(
        """
        INSERT INTO users (email, password_hash)
        VALUES (?, ?)
        """,
        ("other@test.com", "not-used"),
    )
    other_user_id = other_user.lastrowid
    other_category = conn.execute(
        """
        INSERT INTO categories (user_id, name, is_default)
        VALUES (?, 'Food', 1)
        """,
        (other_user_id,),
    )
    conn.execute(
        """
        INSERT INTO transactions
            (user_id, category_id, amount, type, description, transaction_date)
        VALUES (?, ?, ?, 'expense', ?, ?)
        """,
        (
            other_user_id,
            other_category.lastrowid,
            9999.00,
            "Other user's expense",
            transaction_date,
        ),
    )

    conn.commit()
    conn.close()

    response = client.get("/dashboard")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<p class="summary-amount income-amount">$1000.00</p>' in page
    assert '<p class="summary-amount expense-amount">$200.00</p>' in page
    assert '<p class="summary-amount">$300.00</p>' in page
    assert "$9999.00" not in page
    assert "Other user's expense" not in page


def test_dashboard_shows_unread_alerts_and_only_five_recent_transactions(client):
    register_and_login(client)
    user_id, category_id = get_user_and_food_category()
    month = datetime.now().strftime("%Y-%m")

    conn = get_db_connection()
    budget_cursor = conn.execute(
        """
        INSERT INTO budgets (user_id, category_id, monthly_limit, month)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, category_id, 100.00, month),
    )
    budget_id = budget_cursor.lastrowid

    conn.execute(
        """
        INSERT INTO alerts (user_id, budget_id, alert_type, is_read)
        VALUES (?, ?, 'near limit', 0)
        """,
        (user_id, budget_id),
    )
    conn.execute(
        """
        INSERT INTO alerts (user_id, budget_id, alert_type, is_read)
        VALUES (?, ?, 'over limit', 1)
        """,
        (user_id, budget_id),
    )

    for day in range(1, 7):
        conn.execute(
            """
            INSERT INTO transactions
                (user_id, category_id, amount, type, description, transaction_date)
            VALUES (?, ?, ?, 'expense', ?, ?)
            """,
            (
                user_id,
                category_id,
                float(day),
                f"Recent transaction {day}",
                f"{month}-{day:02d}",
            ),
        )

    conn.commit()
    conn.close()

    response = client.get("/dashboard")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Food: Near Limit" in page
    assert "Food: Over Limit" not in page

    for day in range(2, 7):
        assert f"Recent transaction {day}" in page
    assert "Recent transaction 1" not in page
