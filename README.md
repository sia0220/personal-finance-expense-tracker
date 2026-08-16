# Personal Finance Expense Tracker

This is a Flask and SQLite web application for tracking personal expenses, income, budgets, alerts, and reports.

## Technology Stack

- Frontend: HTML and CSS
- Backend: Python with Flask
- Database: SQLite
- Version Control: GitHub

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/sia0220/personal-finance-expense-tracker.git
cd personal-finance-expense-tracker
```

### 2. Create a virtual environment

On Windows:

```powershell
python -m venv .venv
```

On macOS/Linux:

```bash
python3 -m venv .venv
```

### 3. Activate the virtual environment

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

On Windows Command Prompt:

```text
.venv\Scripts\activate.bat
```

On macOS/Linux:

```bash
source .venv/bin/activate
```

### 4. Install the required dependencies

```bash
pip install -r requirements.txt
```

### 5. Initialize the SQLite database

Run:

```bash
python database.py
```

This creates the local `finance_tracker.db` database from `schema.sql`.

### 6. Start the application

```bash
python app.py
```

### 7. Open the application

Open this address in a web browser:

```text
http://127.0.0.1:5000
```

Register a new account, then log in to use the dashboard, transactions, budgets, alerts, and reports features.

## Running Tests

With the virtual environment active, run:

```bash
python -m pytest -v
```

On Windows, the virtual environment's Python can also be used directly:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

## Troubleshooting

### Python is not recognized or cannot be found

Check that Python is installed:

```bash
python --version
```

If that command does not work on macOS/Linux, try:

```bash
python3 --version
```

If Python is installed but the command is still not recognized, make sure Python is added to the system PATH.

### The virtual environment will not activate on Windows PowerShell

Try:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks the activation script, you can still run the virtual environment's Python directly without activating it:

```powershell
.\.venv\Scripts\python.exe app.py
```

You can also run tests directly with:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

### A module such as Flask or pytest is missing

Make sure the virtual environment is active, then install the dependencies again:

```bash
pip install -r requirements.txt
```

### Database tables are missing or the database cannot be opened

Make sure you are running commands from the project root, then initialize the database:

```bash
python database.py
```

The `schema.sql` file must remain in the project folder because it is used to create the database structure.

### The application does not open in the browser

Make sure the Flask application is still running in the terminal:

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

Keep the terminal running while using the application.

### Port 5000 is already in use

Another Flask application may already be running. Stop the older Flask process or close the terminal that is running it, then start the application again.

### Tests do not run

First confirm that the project dependencies are installed:

```bash
pip install -r requirements.txt
```

Then run:

```bash
python -m pytest -v
```

### Local database or environment files appear in Git changes

Do not commit local environment or database files such as:

- `.venv/`
- `finance_tracker.db`
- `.env`
- `__pycache__/`
- `.pytest_cache/`

The database is recreated from the committed `schema.sql` file.
