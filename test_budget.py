import sqlite3
import pytest
import budget_service

def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    with open("schema.sql", "r") as f:
        conn.executescript(f.read())
    conn.execute(
        "INSERT INTO users (user_id, email, password_hash) VALUES (1, 'a@b.com', 'x')"
    )
    conn.execute(
        "INSERT INTO categories (category_id, user_id, name) VALUES (1, 1, 'Food')"
    )
    conn.commit()
    return conn

def add_budget(conn, limit, month="2026-07"):
    cur = conn.execute(
        "INSERT INTO budgets (user_id, category_id, monthly_limit, month) VALUES (1, 1, ?, ?)",
        (limit, month),
    )
    conn.commit()
    return cur.lastrowid

def add_expense(conn, amount, date="2026-07-15"):
    conn.execute(
        """INSERT INTO transactions (user_id, category_id, amount, type, transaction_date)
           VALUES (1, 1, ?, 'expense', ?)""",
        (amount, date),
    )
    conn.commit()

def test_tc_b01_below_limit_no_alert():
    conn = make_conn()
    add_budget(conn, 200)
    add_expense(conn, 90)
    assert budget_service.check_threshold(90, 200) is None

def test_tc_b02_just_below_near_limit():
    assert budget_service.check_threshold(79, 100) is None

def test_tc_b03_near_limit_at_exactly_80():
    assert budget_service.check_threshold(80, 100) == "near limit"

def test_tc_b04_within_near_limit_band():
    assert budget_service.check_threshold(99, 100) == "near limit"

def test_tc_b05_over_limit_at_exactly_100():
    assert budget_service.check_threshold(100, 100) == "over limit"

def test_tc_b06_above_limit():
    assert budget_service.check_threshold(101, 100) == "over limit"

def test_tc_b07_alert_created_on_add():
    conn = make_conn()
    bid = add_budget(conn, 100)
    add_expense(conn, 70)
    budget_service.evaluate_budget(conn, 1, bid)
    assert conn.execute("SELECT COUNT(*) c FROM alerts").fetchone()["c"] == 0
    add_expense(conn, 15)
    budget_service.evaluate_budget(conn, 1, bid)
    row = conn.execute("SELECT alert_type FROM alerts").fetchone()
    assert row["alert_type"] == "near limit"

def test_tc_b08_state_clears_after_delete():
    conn = make_conn()
    bid = add_budget(conn, 100)
    add_expense(conn, 100)
    state = budget_service.evaluate_budget(conn, 1, bid)
    assert state["alert_type"] == "over limit"
    conn.execute("DELETE FROM transactions WHERE amount = 100")
    conn.commit()
    add_expense(conn, 70)
    state = budget_service.evaluate_budget(conn, 1, bid)
    assert state["alert_type"] is None

def test_tc_b09_invalid_limit_rejected():
    conn = make_conn()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO budgets (user_id, category_id, monthly_limit, month) VALUES (1,1,0,'2026-07')"
        )
        conn.commit()

def test_tc_b10_spending_scoped_correctly():
    conn = make_conn()
    conn.execute(
        "INSERT INTO categories (category_id, user_id, name) VALUES (2, 1, 'Transport')"
    )
    add_budget(conn, 100)
    add_expense(conn, 50)
    conn.execute(
        """INSERT INTO transactions (user_id, category_id, amount, type, transaction_date)
           VALUES (1, 2, 40, 'expense', '2026-07-10')"""
    )
    conn.execute(
        """INSERT INTO transactions (user_id, category_id, amount, type, transaction_date)
           VALUES (1, 1, 40, 'expense', '2026-06-10')"""
    )
    conn.commit()
    spending = budget_service.calc_spending(conn, 1, 1, "2026-07")
    assert spending == 50
