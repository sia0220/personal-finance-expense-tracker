def get_spending_by_category(conn, user_id):
    # Return total expense spending grouped by category for the logged in user.
    rows = conn.execute(
        """
        SELECT
            c.name AS category_name,
            ROUND(SUM(t.amount), 2) AS total_spent
        FROM transactions AS t
        JOIN categories AS c
            ON c.category_id = t.category_id
            AND c.user_id = t.user_id
        WHERE t.user_id = ?
            AND t.type = 'expense'
        GROUP BY t.category_id, c.name
        ORDER BY total_spent DESC, c.name ASC
        """,
        (user_id,),
    ).fetchall()

    return [
        {
            "category_name": row["category_name"],
            "total_spent": float(row["total_spent"])
        }
        for row in rows
    ]

def get_monthly_spending(conn, user_id):
    # Return total expense spending grouped by month for the logged in user.
    rows = conn.execute(
        """
        SELECT
            strftime('%Y-%m', transaction_date) AS month,
            ROUND(SUM(amount), 2) AS total_spent
        FROM transactions
        WHERE user_id = ?
            AND type = 'expense'
        GROUP BY strftime('%Y-%m', transaction_date)
        ORDER BY month ASC
        """,
        (user_id,),
    ).fetchall()

    return [
        {
            "month": row["month"],
            "total_spent": float(row["total_spent"]),
        }
        for row in rows
    ]

def get_income_expense_totals(conn, user_id):
    # Return total income and total expenses for the logged in user.
    row = conn.execute(
        """
        SELECT
            COALESCE(
                SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END),
                0
            ) AS total_income,
            COALESCE(
                SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END),
                0
            ) AS total_expenses
        FROM transactions
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()

    return {
        "total_income": round(float(row["total_income"]), 2),
        "total_expenses": round(float(row["total_expenses"]), 2),
    }