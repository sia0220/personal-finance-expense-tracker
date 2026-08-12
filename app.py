import os
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_bcrypt import Bcrypt
from functools import wraps
import sqlite3
from database import init_db, get_db_connection, create_default_categories
from transaction_validation import validate_transaction_form


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-later")

# Added BY DEVIN ****
bcrypt = Bcrypt(app) #Initializing Bcrypt for hashing
# **************
# Added BY DEVIN *****
def login_required(f): 
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function
#****************
@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
# Added BY DEVIN *****
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
# *************************
# ADDED BY DEVIN ********
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
#*******
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

    cursor = conn.execute(
        """
        DELETE FROM transactions
        WHERE transaction_id = ?
            AND user_id = ?
        """,
        (transaction_id, user_id)
    )

    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        flash("Transaction not found.")
    else:
        flash("Transaction deleted successfully.")

    return redirect(url_for("transactions"))

@app.route("/budgets")
@login_required
def budgets():
    return render_template("budgets.html")

@app.route("/reports")
@login_required
def reports():
    return render_template("reports.html")

@app.route("/logout")
def logout():
    session.clear() 
    flash("Successfully logged out.") 
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)