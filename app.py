import os
import math
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_bcrypt import Bcrypt
from functools import wraps
import sqlite3
from database import init_db, get_db_connection, create_default_categories
from transaction_validation import validate_transaction_form
import report_service
import budget_service


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-later")

bcrypt = Bcrypt(app)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def current_user_id():
    return session.get("user_id")


def recalc_budget_after_transaction(conn, user_id, category_id, transaction_date):
    month = transaction_date[:7]
    budget = conn.execute(
        """
        SELECT budget_id FROM budgets
        WHERE user_id = ? AND category_id = ? AND month = ?
        """,
        (user_id, category_id, month),
    ).fetchone()
    if budget is not None:
        budget_service.evaluate_budget(conn, user_id, budget["budget_id"])
        conn.commit()


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        if not email or not password:
            flash("Email and password are required.")
            return redirect(url_for("login"))

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user and bcrypt.check_password_hash(user["password_hash"], password):
            session["user_id"] = user["user_id"]
            flash("Successfully logged in.")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password:
            flash("Email and password are required.")
            return redirect(url_for("register"))

        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email, hashed_pw)
            )
            new_user_id = cursor.lastrowid
            create_default_categories(conn, new_user_id)
            conn.commit()

            flash("Registration successful.")
            return redirect(url_for('login'))

        except sqlite3.IntegrityError:
            conn.rollback()
            flash("Email is already registered.")
            return redirect(url_for('register'))
        except Exception:
            conn.rollback()
            flash("An error occurred during registration. Please try again.")
            return redirect(url_for('register'))
        finally:
            conn.close()

    return render_template('register.html')


@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    conn = get_db_connection()

    current_month = datetime.now().strftime("%Y-%m")

    totals = conn.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0)
                AS total_income,
            COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0)
                AS total_expenses
        FROM transactions
        WHERE user_id = ?
          AND substr(transaction_date, 1, 7) = ?
        """,
        (user_id, current_month),
    ).fetchone()

    recent_transactions = conn.execute(
        """
        SELECT
            t.transaction_id,
            t.amount,
            t.type,
            t.description,
            t.transaction_date,
            c.name AS category_name
        FROM transactions AS t
        JOIN categories AS c
            ON c.category_id = t.category_id
            AND c.user_id = t.user_id
        WHERE t.user_id = ?
        ORDER BY t.transaction_date DESC, t.transaction_id DESC
        LIMIT 5
        """,
        (user_id,),
    ).fetchall()

    active_alerts = conn.execute(
        """
        SELECT
            a.alert_id,
            a.alert_type,
            a.triggered_at,
            c.name AS category_name
        FROM alerts AS a
        JOIN budgets AS b
            ON b.budget_id = a.budget_id
            AND b.user_id = a.user_id
        JOIN categories AS c
            ON c.category_id = b.category_id
            AND c.user_id = a.user_id
        WHERE a.user_id = ? AND a.is_read = 0
        ORDER BY a.triggered_at DESC, a.alert_id DESC
        """,
        (user_id,),
    ).fetchall()

    budget_overview = budget_service.get_budget_overview(conn, user_id)
    remaining_budget = sum(
        float(budget["monthly_limit"]) - float(budget["spending"])
        for budget in budget_overview
        if budget["month"] == current_month
    )

    conn.close()

    return render_template(
        "dashboard.html",
        total_income=float(totals["total_income"]),
        total_expenses=float(totals["total_expenses"]),
        remaining_budget=remaining_budget,
        recent_transactions=recent_transactions,
        alerts=active_alerts,
    )


@app.route("/transactions", methods=["GET", "POST"])
@login_required
def transactions():
    user_id = session["user_id"]
    conn = get_db_connection()

    categories = conn.execute(
        """
        SELECT category_id, name
        FROM categories
        WHERE user_id = ?
        ORDER BY name COLLATE NOCASE ASC
        """,
        (user_id,),
    ).fetchall()

    if request.method == "POST":
        errors, cleaned_data = validate_transaction_form(request.form)

        if not errors:
            category = conn.execute(
                """
                SELECT category_id
                FROM categories
                WHERE category_id = ? AND user_id = ?
                """,
                (cleaned_data["category_id"], user_id),
            ).fetchone()

            if category is None:
                errors.append("Please select a valid category.")

        if errors:
            conn.close()
            for error in errors:
                flash(error)
            return redirect(url_for("transactions"))

        conn.execute(
            """
            INSERT INTO transactions (
            user_id,
            category_id,
            amount,
            type,
            description,
            transaction_date
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                cleaned_data["category_id"],
                cleaned_data["amount"],
                cleaned_data["type"],
                cleaned_data["description"],
                cleaned_data["transaction_date"]
            ),
        )
        conn.commit()

        recalc_budget_after_transaction(
            conn, user_id, cleaned_data["category_id"], cleaned_data["transaction_date"]
        )
        conn.close()

        flash("Transaction added successfully.")
        return redirect(url_for("transactions"))

    search = request.args.get("search", "").strip()
    selected_category_id = request.args.get("category_id", "").strip()
    selected_type = request.args.get("type", "").strip().lower()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    query = """
        SELECT
            t.transaction_id,
            t.amount,
            t.type,
            t.description,
            t.transaction_date,
            t.category_id,
            c.name AS category_name
        FROM transactions AS t
        JOIN categories AS c
            ON c.category_id = t.category_id
            AND c.user_id = t.user_id
        WHERE t.user_id = ?
        """

    parameters = [user_id]

    if search:
        query += " AND COALESCE(t.description, '') LIKE ?"
        parameters.append(f"%{search}%")

    if selected_category_id:
        try:
            category_id = int(selected_category_id)
            if category_id > 0:
                query += " AND t.category_id = ?"
                parameters.append(category_id)
            else:
                selected_category_id = ""
        except ValueError:
            selected_category_id = ""

    if selected_type in {"income", "expense"}:
        query += " AND t.type = ?"
        parameters.append(selected_type)
    else:
        selected_type = ""

    if start_date:
        query += " AND t.transaction_date >= ?"
        parameters.append(start_date)

    if end_date:
        query += " AND t.transaction_date <= ?"
        parameters.append(end_date)

    query += """
        ORDER BY
            t.transaction_date DESC,
            t.transaction_id DESC
        """

    transaction_rows = conn.execute(query, parameters).fetchall()
    conn.close()

    return render_template(
        "transactions.html",
        categories=categories,
        transactions=transaction_rows,
        search=search,
        selected_category_id=selected_category_id,
        selected_type=selected_type,
        start_date=start_date,
        end_date=end_date
    )


@app.route("/transactions/<int:transaction_id>/edit", methods=["GET", "POST"])
@login_required
def edit_transaction(transaction_id):
    user_id = session["user_id"]
    conn = get_db_connection()

    transaction = conn.execute(
        """
        SELECT *
        FROM transactions
        WHERE transaction_id = ?
            AND user_id = ?
        """,
        (transaction_id, user_id),
    ).fetchone()

    if transaction is None:
        conn.close()
        flash("Transaction not found.")
        return redirect(url_for("transactions"))

    categories = conn.execute(
        """
        SELECT category_id, name
        FROM categories
        WHERE user_id = ?
        ORDER BY name COLLATE NOCASE ASC
        """,
        (user_id,),
    ).fetchall()

    if request.method == "POST":
        errors, cleaned_data = validate_transaction_form(request.form)

        if not errors:
            category = conn.execute(
                """
                SELECT category_id
                FROM categories
                WHERE category_id = ?
                    AND user_id = ?
                """,
                (cleaned_data["category_id"], user_id),
            ).fetchone()

            if category is None:
                errors.append("Please select a valid category.")

        if errors:
            conn.close()
            for error in errors:
                flash(error)
            return redirect(url_for("edit_transaction", transaction_id=transaction_id))

        old_category_id = transaction["category_id"]
        old_date = transaction["transaction_date"]

        conn.execute(
            """
            UPDATE transactions
            SET
                category_id = ?,
                amount = ?,
                type = ?,
                description = ?,
                transaction_date = ?
            WHERE transaction_id = ?
                AND user_id = ?
            """,
            (
                cleaned_data["category_id"],
                cleaned_data["amount"],
                cleaned_data["type"],
                cleaned_data["description"],
                cleaned_data["transaction_date"],
                transaction_id,
                user_id
            ),
        )
        conn.commit()

        recalc_budget_after_transaction(
            conn, user_id, cleaned_data["category_id"], cleaned_data["transaction_date"]
        )
        if old_category_id != cleaned_data["category_id"] or old_date[:7] != cleaned_data["transaction_date"][:7]:
            recalc_budget_after_transaction(conn, user_id, old_category_id, old_date)
        conn.close()

        flash("Transaction updated successfully.")
        return redirect(url_for("transactions"))

    conn.close()

    return render_template(
        "edit_transaction.html",
        transaction=transaction,
        categories=categories
    )


@app.route("/transactions/<int:transaction_id>/delete", methods=["POST"])
@login_required
def delete_transaction(transaction_id):
    user_id = session["user_id"]
    conn = get_db_connection()

    transaction = conn.execute(
        "SELECT category_id, transaction_date FROM transactions WHERE transaction_id = ? AND user_id = ?",
        (transaction_id, user_id),
    ).fetchone()

    cursor = conn.execute(
        """
        DELETE FROM transactions
        WHERE transaction_id = ?
            AND user_id = ?
        """,
        (transaction_id, user_id)
    )
    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        flash("Transaction not found.")
        return redirect(url_for("transactions"))

    if transaction is not None:
        recalc_budget_after_transaction(
            conn, user_id, transaction["category_id"], transaction["transaction_date"]
        )
    conn.close()

    flash("Transaction deleted successfully.")
    return redirect(url_for("transactions"))


@app.route("/budgets")
@login_required
def budgets():
    user_id = current_user_id()
    conn = get_db_connection()
    budget_list = budget_service.get_budget_overview(conn, user_id)
    categories = conn.execute(
        "SELECT category_id, name FROM categories WHERE user_id = ? ORDER BY name",
        (user_id,),
    ).fetchall()
    conn.close()
    return render_template(
        "budgets.html", budgets=budget_list, categories=categories
    )


@app.route("/budgets/create", methods=["POST"])
@login_required
def create_budget():
    user_id = current_user_id()
    category_id = request.form.get("category_id", type=int)
    month = request.form.get("month", "").strip()
    monthly_limit = request.form.get("monthly_limit", type=float)

    if not category_id or not month:
        flash("Please select a category and month.")
        return redirect(url_for("budgets"))

    try:
        parsed_month = datetime.strptime(month, "%Y-%m")
        if parsed_month.strftime("%Y-%m") != month:
            raise ValueError
    except ValueError:
        flash("Please enter a valid month.")
        return redirect(url_for("budgets"))

    if monthly_limit is None or not math.isfinite(monthly_limit) or monthly_limit <= 0:
        flash("Monthly limit must be greater than 0.")
        return redirect(url_for("budgets"))

    conn = get_db_connection()
    owns_category = conn.execute(
        "SELECT 1 FROM categories WHERE category_id = ? AND user_id = ?",
        (category_id, user_id),
    ).fetchone()
    if owns_category is None:
        conn.close()
        flash("Please select a valid category.")
        return redirect(url_for("budgets"))

    try:
        cur = conn.execute(
            """
            INSERT INTO budgets (user_id, category_id, monthly_limit, month)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, category_id, monthly_limit, month),
        )
        conn.commit()
        budget_service.evaluate_budget(conn, user_id, cur.lastrowid)
        conn.commit()
        flash("Budget created.")
    except sqlite3.IntegrityError:
        conn.rollback()
        flash("Budget already exists for this category and month.")
    finally:
        conn.close()
    return redirect(url_for("budgets"))


@app.route("/alerts")
@login_required
def alerts():
    user_id = current_user_id()
    conn = get_db_connection()
    alert_rows = conn.execute(
        """
        SELECT a.alert_id, a.alert_type, a.triggered_at, a.is_read,
               c.name AS category_name
        FROM alerts a
        JOIN budgets b ON b.budget_id = a.budget_id
        JOIN categories c ON c.category_id = b.category_id
        WHERE a.user_id = ?
        ORDER BY a.triggered_at DESC, a.alert_id DESC
        """,
        (user_id,),
    ).fetchall()
    conn.close()
    return render_template("alerts.html", alerts=alert_rows)


@app.route("/reports")
@login_required
def reports():
    user_id = session["user_id"]
    conn = get_db_connection()

    category_spending = report_service.get_spending_by_category(conn, user_id)
    monthly_spending = report_service.get_monthly_spending(conn, user_id)
    totals = report_service.get_income_expense_totals(conn, user_id)

    conn.close()

    category_labels = [item["category_name"] for item in category_spending]
    category_values = [item["total_spent"] for item in category_spending]
    month_labels = [item["month"] for item in monthly_spending]
    month_values = [item["total_spent"] for item in monthly_spending]

    return render_template(
        "reports.html",
        category_spending=category_spending,
        monthly_spending=monthly_spending,
        totals=totals,
        category_labels=category_labels,
        category_values=category_values,
        month_labels=month_labels,
        month_values=month_values
    )


@app.route("/logout")
def logout():
    session.clear()
    flash("Successfully logged out.")
    return redirect(url_for('login'))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
