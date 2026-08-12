import os
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_bcrypt import Bcrypt
from functools import wraps
import sqlite3
from database import init_db, get_db_connection, create_default_categories
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
            flash("Successfully logged in")
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

            flash("Registration successful")
            return redirect(url_for('login'))

        except sqlite3.IntegrityError:
            conn.rollback()
            flash("Email is already registered")
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
    return render_template("dashboard.html")


@app.route("/transactions")
@login_required
def transactions():
    return render_template("transactions.html")


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
    if monthly_limit is None or monthly_limit <= 0:
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
    return render_template("reports.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("successfully logged out")
    return redirect(url_for('login'))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
