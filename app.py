from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_bcrypt import Bcrypt
from functools import wraps
import sqlite3
from database import init_db, get_db_connection, create_default_categories
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-later")

# Added BY DEVIN ****
bcrypt = Bcrypt(app) #Initializing Bcrypt for hashing
# **************
# Added BY DEVIN *****
def login_required(f): # Decorator to protect private routes
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

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        
        if user and bcrypt.check_password_hash(user["password_hash"], password):
            session["user_id"] = user["user_id"]
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
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email, hashed_pw)
            )
            conn.commit()
            
            # Fetch the newly created user_id to assign default categories
            user_id = cursor.lastrowid
            create_default_categories(user_id)
            
            flash("Registration successful! Please log in.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            # Triggers if the email is not unique (violates the UNIQUE constraint in the schema)
            flash("Email is already registered.")
            return redirect(url_for("register"))
        finally:
            conn.close()
            
    return render_template("register.html")
#*******
@app.route("/dashboard")
def dashboard():
    #Check if your user session variable exists
    # Change 'user_id' to whatever key you used when you set up the login route
    if 'user_id' not in session: 
        flash("Please log in to access this page")
        return redirect(url_for('login'))
    return render_template("dashboard.html")

@app.route("/transactions")
def transactions():
    if 'user_id' not in session: 
        flash("Please log in to access this page")
        return redirect(url_for('login'))
    return render_template("transactions.html")

@app.route("/budgets")
def budgets():
    if 'user_id' not in session: 
        flash("Please log in to access this page")
        return redirect(url_for('login'))
    return render_template("budgets.html")

@app.route("/reports")
def reports():
    if 'user_id' not in session: 
        flash("Please log in to access this page")
        return redirect(url_for('login'))
    return render_template("reports.html")
#***Added BY DEVIN ********
@app.route("/logout")
def logout():
    session.clear() 
    
    flash("successfully logged out") 
    
    return redirect(url_for('login'))
#****************************
if __name__ == "__main__":
    init_db()
    app.run(debug=True)