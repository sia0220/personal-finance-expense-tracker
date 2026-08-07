from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    session,
)
from database import init_db, get_db_connection
import budget_service
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-later")

def current_user_id():
    return session.get("user_id", 1)

@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        flash("Login logic will be implemented in Sprint 1.")
        return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        flash("Registration logic will be implemented in Sprint 1.")
        return redirect(url_for("register"))
    return render_template("register.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/transactions")
def transactions():
    return render_template("transactions.html")

@app.route("/budgets")
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
def create_budget():
    user_id = current_user_id()
    category_id = request.form.get("category_id", type=int)
    month = request.form.get("month", "").strip()
    monthly_limit = request.form.get("monthly_limit", type=float)

    if not category_id or not month:
        flash("Please select a category and month.")
        return redirect(url_for("budgets"))
    if monthly_limit is None or monthly_limit <= 0:
        flash("Monthly limit must be greater than 0.")
        return redirect(url_for("budgets"))

    conn = get_db_connection()
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
    except Exception:
        flash("Budget already exists for this category and month.")
    finally:
        conn.close()
    return redirect(url_for("budgets"))

@app.route("/alerts")
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
def reports():
    return render_template("reports.html")

@app.route("/logout")
def logout():
    flash("Logout logic will be implemented in Sprint 1.")
    return redirect(url_for("login"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
