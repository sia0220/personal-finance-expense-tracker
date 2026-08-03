NEAR_LIMIT_THRESHOLD = 0.80
OVER_LIMIT_THRESHOLD = 1.00

def calc_spending(conn, user_id, category_id, month):
    row = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE user_id = ?
          AND category_id = ?
          AND type = 'expense'
          AND strftime('%Y-%m', transaction_date) = ?
        """,
        (user_id, category_id, month),
    ).fetchone()
    return float(row["total"])

def get_percent_used(spending, monthly_limit):
    if monthly_limit <= 0:
        return 0.0
    return spending / monthly_limit

def check_threshold(spending, monthly_limit):
    percent = get_percent_used(spending, monthly_limit)
    if percent >= OVER_LIMIT_THRESHOLD:
        return "over limit"
    if percent >= NEAR_LIMIT_THRESHOLD:
        return "near limit"
    return None

def evaluate_budget(conn, user_id, budget_id):
    budget = conn.execute(
        "SELECT * FROM budgets WHERE budget_id = ? AND user_id = ?",
        (budget_id, user_id),
    ).fetchone()
    if budget is None:
        return None

    spending = calc_spending(
        conn, user_id, budget["category_id"], budget["month"]
    )
    percent = get_percent_used(spending, budget["monthly_limit"])
    alert_type = check_threshold(spending, budget["monthly_limit"])

    if alert_type is not None:
        _record_alert_if_new(conn, user_id, budget_id, alert_type)

    return {
        "budget_id": budget_id,
        "spending": round(spending, 2),
        "monthly_limit": budget["monthly_limit"],
        "percent": round(percent * 100, 1),
        "alert_type": alert_type,
    }

def _record_alert_if_new(conn, user_id, budget_id, alert_type):
    latest = conn.execute(
        """
        SELECT alert_type FROM alerts
        WHERE budget_id = ? AND user_id = ?
        ORDER BY triggered_at DESC, alert_id DESC
        LIMIT 1
        """,
        (budget_id, user_id),
    ).fetchone()

    if latest is not None and latest["alert_type"] == alert_type:
        return

    conn.execute(
        """
        INSERT INTO alerts (user_id, budget_id, alert_type)
        VALUES (?, ?, ?)
        """,
        (user_id, budget_id, alert_type),
    )

def get_budget_overview(conn, user_id):
    budgets = conn.execute(
        """
        SELECT b.budget_id, b.monthly_limit, b.month,
               c.name AS category_name, b.category_id
        FROM budgets b
        JOIN categories c ON c.category_id = b.category_id
        WHERE b.user_id = ?
        ORDER BY b.month DESC, c.name
        """,
        (user_id,),
    ).fetchall()

    overview = []
    for b in budgets:
        spending = calc_spending(
            conn, user_id, b["category_id"], b["month"]
        )
        percent = get_percent_used(spending, b["monthly_limit"])
        overview.append(
            {
                "budget_id": b["budget_id"],
                "category_name": b["category_name"],
                "monthly_limit": b["monthly_limit"],
                "month": b["month"],
                "spending": round(spending, 2),
                "percent": round(percent * 100, 1),
                "alert_type": check_threshold(spending, b["monthly_limit"]),
            }
        )
    return overview
