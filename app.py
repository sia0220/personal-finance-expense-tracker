import os
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_bcrypt import Bcrypt
from functools import wraps
import sqlite3
from database import init_db, get_db_connection, create_default_categories


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-later")


bcrypt = Bcrypt(app) 

def process_budget_and_alerts(conn, user_id, category_id, month):
    """
    Calculates total spent for a category/month, evaluates alerts, 
    commits changes, and returns the total spent amount.
    """
    if not category_id or not month:
        return 0.0

    # Ensure month is formatted as 'YYYY-MM'
    month = str(month)[:7]

    # 1. Calculate total spent (Single Source of Truth)
    spent_row = conn.execute("""
        SELECT SUM(amount) as total_spent 
        FROM transactions 
        WHERE user_id = ? AND category_id = ? AND type = 'expense' 
        AND strftime('%Y-%m', transaction_date) = ?
    """, (user_id, category_id, month)).fetchone()
    
    spent = spent_row["total_spent"] or 0.0

    # 2. Check if a budget exists
    budget = conn.execute("""
        SELECT budget_id, monthly_limit 
        FROM budgets 
        WHERE user_id = ? AND category_id = ? AND month = ?
    """, (user_id, category_id, month)).fetchone()

    # If no budget exists, we just return the spent amount without updating alerts
    if not budget:
        return spent

    budget_id = budget["budget_id"]
    monthly_limit = budget["monthly_limit"]

    # 3. Determine required alert state
    new_alert_type = 'over limit' if spent >= monthly_limit else ('near limit' if spent >= (monthly_limit * 0.8) else None)

    # 4. Manage alerts table
    existing_alert = conn.execute(
        "SELECT alert_id, alert_type FROM alerts WHERE user_id = ? AND budget_id = ?",
        (user_id, budget_id)
    ).fetchone()

    if new_alert_type:
        if existing_alert:
            if existing_alert["alert_type"] != new_alert_type:
                conn.execute(
                    "UPDATE alerts SET alert_type = ?, is_read = 0, triggered_at = CURRENT_TIMESTAMP WHERE alert_id = ?", 
                    (new_alert_type, existing_alert["alert_id"])
                )
        else:
            conn.execute(
                "INSERT INTO alerts (user_id, budget_id, alert_type) VALUES (?, ?, ?)", 
                (user_id, budget_id, new_alert_type)
            )
    elif existing_alert:
        # Spending dropped below 80% (e.g., transaction deleted/edited)
        conn.execute("DELETE FROM alerts WHERE alert_id = ?", (existing_alert["alert_id"],))

    # 5. Commit alert changes and return spent for frontend use
    conn.commit()
    return spent

def login_required(f): 
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function
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
    # ==========================================
# TODO (Transaction Team): BUDGET ALERT INTEGRATION
# To connect transactions to the budget alert system, please import 
# `process_budget_and_alerts` and integrate it into these routes:
#
# 1. ADD TRANSACTION (/transactions):
#    After executing `conn.commit()` for the INSERT, call:
#    process_budget_and_alerts(conn, user_id, category_id, transaction_date)
#
# 2. EDIT TRANSACTION (/transactions/edit/<id>):
#    BEFORE the UPDATE, fetch the old category_id and transaction_date.
#    After `conn.commit()`, call the helper twice to update both budgets:
#    process_budget_and_alerts(conn, user_id, old_category_id, old_transaction_date)
#    process_budget_and_alerts(conn, user_id, new_category_id, new_transaction_date)
#
# 3. DELETE TRANSACTION (/transactions/delete/<id>):
#    BEFORE the DELETE, fetch the transaction's category_id and transaction_date.
#    After `conn.commit()`, call the helper using those old values so it can 
#    clear any existing alerts if the user's spending drops below the limit.
#    process_budget_and_alerts(conn, user_id, old_category_id, old_transaction_date)
# ==========================================
    return render_template("transactions.html")

@app.route("/budgets", methods=["GET", "POST"])
@login_required
def budgets():
    user_id = session["user_id"]
    conn = get_db_connection()

    if request.method == "POST":
        category_id = request.form.get("category_id")
        month = request.form.get("month")
        raw_limit = request.form.get("monthly_limit")
        
        try:
            monthly_limit = float(raw_limit) if raw_limit else 0.0
        except (ValueError, TypeError):
            monthly_limit = 0.0

        # Validate category ownership
        cat_exists = conn.execute(
            "SELECT 1 FROM categories WHERE category_id = ? AND user_id = ?", 
            (category_id, user_id)
        ).fetchone()

        is_valid_month = (
            bool(month) 
            and len(month) == 7 
            and month[4] == '-' 
            and month[:4].isdigit() 
            and month[5:].isdigit() 
            and (1 <= int(month[5:]) <= 12)
        )

        if not cat_exists:
            flash("Invalid or unauthorized category.")
        elif monthly_limit <= 0:
            flash("Monthly limit must be a positive number greater than zero.")
        elif not is_valid_month:
            flash("Please select a month.")
        else:
            try:
                conn.execute(
                    "INSERT INTO budgets (user_id, category_id, monthly_limit, month) VALUES (?, ?, ?, ?)",
                    (user_id, category_id, monthly_limit, month)
                )
                conn.commit()
                flash("Budget successfully created!")
                
                process_budget_and_alerts(conn, user_id, category_id, month)
            except sqlite3.IntegrityError:
                flash("A budget for this category and month already exists.")

    categories = conn.execute("SELECT * FROM categories WHERE user_id = ?", (user_id,)).fetchall()
    
    user_budgets = conn.execute("""
        SELECT b.budget_id, c.name AS category_name, b.monthly_limit, b.month, b.category_id
        FROM budgets b
        JOIN categories c ON b.category_id = c.category_id
        WHERE b.user_id = ?
        ORDER BY b.month DESC
    """, (user_id,)).fetchall()

    budget_data = []
    for b in user_budgets:
        spent = process_budget_and_alerts(conn, user_id, b["category_id"], b["month"])
        
        budget_data.append({
            "budget_id": b["budget_id"],
            "category_name": b["category_name"],
            "monthly_limit": b["monthly_limit"],
            "month": b["month"],
            "spent": spent,
            "remaining": b["monthly_limit"] - spent
        })

    conn.close()
    return render_template("budgets.html", categories=categories, budgets=budget_data)

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