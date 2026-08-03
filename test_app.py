# Test file for verifying that the authentication workflow and route protection function correctly.
import pytest
from app import app
from database import init_db, get_db_connection

@pytest.fixture
def client():
    """Sets up a test client and initializes a clean database."""
    app.config["TESTING"] = True
    app.secret_key = "test_secret_key"
    
    with app.test_client() as client:
        with app.app_context():
            init_db()
        yield client

@pytest.fixture
def auth_client(client):
    """Fixture that registers and logs in a test user, returning the authenticated client."""
    client.post(
        "/register",
        data={"email": "auth_test@example.com", "password": "password123"},
        follow_redirects=True
    )
    client.post(
        "/login",
        data={"email": "auth_test@example.com", "password": "password123"},
        follow_redirects=True
    )
    return client

# ==========================================
# AUTHENTICATION TESTS
# ==========================================

def test_tc01_register_valid(client):
    # TC-01 | Register | Enter valid email and password | Account is created[cite: 14]
    response = client.post(
        "/register",
        data={"email": "test@example.com", "password": "securepassword"},
        follow_redirects=True
    )
    assert b"Registration successful" in response.data
    
    # Verify in DB
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", ("test@example.com",)).fetchone()
    conn.close()
    assert user is not None

def test_tc02_register_duplicate(client):
    # TC-02 | Register | Enter duplicate email | Error message appears[cite: 14]
    client.post("/register", data={"email": "duplicate@example.com", "password": "pass1"})
    
    response = client.post(
        "/register",
        data={"email": "duplicate@example.com", "password": "pass2"},
        follow_redirects=True
    )
    assert b"Email is already registered" in response.data

def test_tc03_login_valid(client):
    # TC-03 | Login | Enter valid email and password | User goes to dashboard[cite: 14]
    client.post("/register", data={"email": "login@example.com", "password": "mypassword"})
    
    response = client.post(
        "/login",
        data={"email": "login@example.com", "password": "mypassword"},
        follow_redirects=True
    )
    # Check if we got redirected to the dashboard view
    assert response.request.path == "/dashboard"

def test_tc04_login_wrong_password(client):
    # TC-04 | Login | Enter wrong password | Error message appears[cite: 14]
    client.post("/register", data={"email": "wrongpass@example.com", "password": "correct"})
    
    response = client.post(
        "/login",
        data={"email": "wrongpass@example.com", "password": "wrong"},
        follow_redirects=True
    )
    assert b"Invalid email or password" in response.data
    
@pytest.mark.skip(reason="Logout logic pending in Sprint 1")
def test_tc05_logout(auth_client):
    # TC-05 | Logout | Click logout | Session ends and user returns to login[cite: 14]
    response = auth_client.get("/logout", follow_redirects=True)
    assert b"successfully logged out" in response.data
    assert response.request.path == "/login"
    
    # Verify session is cleared by trying to hit protected route
    protected_response = auth_client.get("/dashboard", follow_redirects=True)
    assert b"Please log in to access this page" in protected_response.data


# ==========================================
# TRANSACTION TESTS (Pending Implementation)
# ==========================================

@pytest.mark.skip(reason="Transaction logic pending")
def test_tc06_add_transaction_valid(auth_client):
    # TC-06 | Add Transaction | Enter valid amount, date, category, type, description | Transaction saves to database[cite: 14]
    response = auth_client.post(
        "/transactions",
        data={
            "amount": 50.00,
            "date": "2023-10-01",
            "category_id": 1,
            "type": "expense",
            "description": "Groceries"
        },
        follow_redirects=True
    )
    assert b"Transaction added" in response.data

@pytest.mark.skip(reason="Transaction validation logic pending")
def test_tc07_add_transaction_negative_amount(auth_client):
    # TC-07 | Add Transaction | Enter negative amount | Error message appears[cite: 14]
    response = auth_client.post(
        "/transactions",
        data={"amount": -10.00, "date": "2023-10-01", "category_id": 1, "type": "expense"},
        follow_redirects=True
    )
    assert b"Amount must be greater than 0" in response.data

@pytest.mark.skip(reason="Transaction edit logic pending")
def test_tc08_edit_transaction(auth_client):
    # TC-08 | Edit Transaction | Change amount or category | Transaction updates correctly[cite: 14]
    pass # Implementation details will depend on your route structure (e.g. /transactions/edit/<id>)

@pytest.mark.skip(reason="Transaction delete logic pending")
def test_tc09_delete_transaction(auth_client):
    # TC-09 | Delete Transaction | Delete transaction | Transaction is removed[cite: 14]
    pass

@pytest.mark.skip(reason="Transaction filter logic pending")
def test_tc10_filter_transaction(auth_client):
    # TC-10 | Filter Transaction | Filter by category or date | Correct results display[cite: 14]
    response = auth_client.get("/transactions?category_id=1")
    assert response.status_code == 200


# ==========================================
# BUDGET AND ALERT TESTS (Pending Implementation)
# ==========================================

@pytest.mark.skip(reason="Budget logic pending")
def test_tc11_create_budget(auth_client):
    # TC-11 | Create Budget | Enter category, month, and limit | Budget saves to database[cite: 14]
    response = auth_client.post(
        "/budgets",
        data={"category_id": 1, "month": "2023-10", "monthly_limit": 500.00},
        follow_redirects=True
    )
    assert b"Budget saved" in response.data

@pytest.mark.skip(reason="Alert logic pending")
def test_tc12_near_limit_alert(auth_client):
    # TC-12 | Near Limit Alert | Spending reaches 80% of budget | Near-limit alert appears[cite: 14]
    # To test this, you'll need to create a budget, then post a transaction that hits 80%
    pass 

@pytest.mark.skip(reason="Alert logic pending")
def test_tc13_over_limit_alert(auth_client):
    # TC-13 | Over Limit Alert | Spending reaches or passes 100% | Over-limit alert appears[cite: 14]
    pass


# ==========================================
# REPORT TESTS (Pending Implementation)
# ==========================================

@pytest.mark.skip(reason="Report generation logic pending")
def test_tc14_spending_by_category(auth_client):
    # TC-14 | Spending by Category | Add transactions in different categories | Category totals display correctly[cite: 14]
    response = auth_client.get("/reports")
    assert response.status_code == 200
    # You will eventually assert that specific JSON data or HTML elements are present

@pytest.mark.skip(reason="Report generation logic pending")
def test_tc15_monthly_trend(auth_client):
    # TC-15 | Monthly Trend | Add transactions across months | Monthly summary displays correctly[cite: 14]
    pass