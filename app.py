import os
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_bcrypt import Bcrypt
from functools import wraps
import sqlite3
from database import init_db, get_db_connection, create_default_categories
from transaction_validation import validate_transaction_form


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

@app.route("/transactions", methods=["GET", "POST"])
@login_required
def transactions():
    user_id = session["user_id"]
    conn = get_db_connection()

    # Load only the logged in user's categories.
    categories = conn.execute(
        """
        SELECT category_id, name
        FROM categories
        WHERE user_id = ?
        ORDER BY name COLLATE NOCASE ASC
        """,
        (user_id,),
    ).fetchall()

    # Add a new transaction.
    if request.method == "POST":
        errors, cleaned_data = validate_transaction_form(request.form)

        # Make sure the selected category belongs to this user.
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

        process_budget_and_alerts(
            conn,
            user_id,
            cleaned_data["category_id"],
            cleaned_data["transaction_date"]
        )

        conn.close()

        flash("Transaction added successfully.")
        return redirect(url_for("transactions"))
    
    # Read search/filter values from the URL.
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

    #Search by description.
    if search:
        query += " AND COALESCE(t.description, '') LIKE ?"
        parameters.append(f"%{search}%")

    # Filter by category.
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
    
    # Filter by income or expense.
    if selected_type in {"income", "expense"}:
        query += " AND t.type = ?"
        parameters.append(selected_type)
    else:
        selected_type = ""

    # Filter by start date.
    if start_date:
        query += " AND t.transaction_date >= ?"
        parameters.append(start_date)

    # Filter by end date.
    if end_date:
        query += " AND t.transaction_date <= ?"
        parameters.append(end_date)
    
    query += """
        ORDER BY
            t.transaction_date DESC,
            t.transaction_id DESC
        """

    transaction_rows = conn.execute(
        query,
        parameters,
    ).fetchall()

    conn.close()

    return render_template(
        "transactions.html",
        categories = categories,
        transactions = transaction_rows,
        search = search,
        selected_category_id = selected_category_id,
        selected_type = selected_type,
        start_date = start_date,
        end_date = end_date
    )

@app.route(
        "/transactions/<int:transaction_id>/edit",
        methods = ["GET", "POST"]
)
@login_required
def edit_transaction(transaction_id):
    user_id = session["user_id"]
    conn = get_db_connection()

    # Only retrieve a transaction owned by the logged in user.
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

    old_category_id = transaction["category_id"]
    old_transaction_date = transaction["transaction_date"]

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

        # Make sure the chosen category belongs to this user.
        if not errors:
            category = conn.execute(
                """
                SELECT category_id
                FROM categories
                WHERE category_id = ?
                    AND user_id = ?
                """,
                (
                    cleaned_data["category_id"],
                    user_id
                ),
            ).fetchone()

            if category is None:
                errors.append("Please select a valid category.")

        if errors:
            conn.close()

            for error in errors:
                flash(error)

            return redirect(
                url_for(
                    "edit_transaction",
                    transaction_id = transaction_id
                )
            )
        
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

        process_budget_and_alerts(conn, user_id, old_category_id, old_transaction_date)
        process_budget_and_alerts(conn, user_id, cleaned_data["category_id"], cleaned_data["transaction_date"])

        conn.close()

        flash("Transaction updated successfully.")
        return redirect(url_for("transactions"))
    
    conn.close()

    return render_template(
        "edit_transaction.html",
        transaction = transaction,
        categories = categories
    )

@app.route(
        "/transactions/<int:transaction_id>/delete",
        methods = ["POST"]
)
@login_required
def delete_transaction(transaction_id):
    user_id = session["user_id"]
    conn = get_db_connection()

    # 1. Collect the needed information before deletion
    transaction = conn.execute(
        """
        SELECT category_id, transaction_date
        FROM transactions
        WHERE transaction_id = ? AND user_id = ?
        """,
        (transaction_id, user_id)
    ).fetchone()

    if transaction is None:
        conn.close()
        flash("Transaction not found.")
        return redirect(url_for("transactions"))

    category_id = transaction["category_id"]
    transaction_date = transaction["transaction_date"]

    # 2. Delete the transaction
    conn.execute(
        """
        DELETE FROM transactions
        WHERE transaction_id = ?
            AND user_id = ?
        """,
        (transaction_id, user_id)
    )

    # 3. Update/recalculate budget and alerts using the collected info
    process_budget_and_alerts(conn, user_id, category_id, transaction_date)

    conn.commit()
    conn.close()

    flash("Transaction deleted successfully.")
    return redirect(url_for("transactions"))

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
            flash("Please select a valid month in YYYY-MM format.")
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