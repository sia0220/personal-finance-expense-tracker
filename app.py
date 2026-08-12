import os
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_bcrypt import Bcrypt
from functools import wraps
import sqlite3
from database import init_db, get_db_connection, create_default_categories


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-later")


bcrypt = Bcrypt(app) 

def check_and_update_alerts(conn, user_id, budget_id, monthly_limit, spent):
    """
    Evaluates spending against the budget limit and generates alerts.
    Expects the spent amount to be calculated prior to calling.
    """
    # 1. Determine the required alert state
    new_alert_type = None
    if spent >= monthly_limit:
        new_alert_type = 'over limit'
    elif spent >= (monthly_limit * 0.8):
        new_alert_type = 'near limit'
        
    # 2. Insert or update the alerts table
    if new_alert_type:
        existing_alert = conn.execute("""
            SELECT alert_id, alert_type FROM alerts 
            WHERE user_id = ? AND budget_id = ?
        """, (user_id, budget_id)).fetchone()
        
        if existing_alert:
            # Only update if the alert severity has changed
            if existing_alert["alert_type"] != new_alert_type:
                conn.execute("""
                    UPDATE alerts 
                    SET alert_type = ?, is_read = 0, triggered_at = CURRENT_TIMESTAMP 
                    WHERE alert_id = ?
                """, (new_alert_type, existing_alert["alert_id"]))
        else:
            # Insert a brand new alert
            conn.execute("""
                INSERT INTO alerts (user_id, budget_id, alert_type) 
                VALUES (?, ?, ?)
            """, (user_id, budget_id, new_alert_type))

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
    return render_template("transactions.html")

@app.route("/budgets")
@login_required
def budgets():
    user_id = session["user_id"]
    conn = get_db_connection()
    if request.method == "POST":
        category_id = request.form.get("category_id")
        monthly_limit = float(request.form.get("monthly_limit"))
        month = request.form.get("month")

        try: 
            conn.execute(
                "INSERT INTO budgets (user_id, category_id, monthly_limit, month) VALUES (?, ?, ?, ?)",
                (user_id, category_id, monthly_limit, month)
            )
            conn.commit()
            flash("Budget successfully created!")
        except sqlite3.IntegrityError:
            flash("A budget for this category and month already exists.")
            
    # Fetch categories for the dropdown menu in the form
    categories = conn.execute("SELECT * FROM categories WHERE user_id = ?", (user_id,)).fetchall()
    
    # Fetch all budgets for the user
    user_budgets = conn.execute("""
        SELECT b.budget_id, c.name AS category_name, b.monthly_limit, b.month, b.category_id
        FROM budgets b
        JOIN categories c ON b.category_id = c.category_id
        WHERE b.user_id = ?
        ORDER BY b.month DESC
    """, (user_id,)).fetchall()
    
    # Budget Calculation Logic: Compare spent vs limit
    budget_data = []
    for b in user_budgets:
        spent_row = conn.execute("""
            SELECT SUM(amount) as total_spent 
            FROM transactions 
            WHERE user_id = ? AND category_id = ? AND type = 'expense' AND strftime('%Y-%m', transaction_date) = ?
        """, (user_id, b["category_id"], b["month"])).fetchone()
        
        spent = spent_row["total_spent"] or 0.0
        remaining = b["monthly_limit"] - spent

        check_and_update_alerts(conn, user_id, b["budget_id"], b["monthly_limit"], spent) #Alert check and update helper function addition
        
        budget_data.append({
            "budget_id": b["budget_id"],
            "category_name": b["category_name"],
            "monthly_limit": b["monthly_limit"],
            "month": b["month"],
            "spent": spent,
            "remaining": remaining
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