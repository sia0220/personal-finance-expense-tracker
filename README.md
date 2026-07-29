# Personal Finance Expense Tracker

This is a Flask and SQLite web application for tracking personal expenses, income, budgets, alerts, and reports.

## Technology Stack

- Frontend: HTML and CSS
- Backend: Python with Flask
- Database: SQLite
- Version Control: GitHub

## Setup Instructions

1. Clone the repository.

2. Create a virtual environment:

'''bash
python3 -m venv .venv
'''

3. Activate the virtual environment on macOS:

'''bash
source .venv/bin/activate
'''

For Windows:

'''bash
.venv\Scripts\activate
'''

4. Install the required dependencies:

'''bash
pip install -r requirements.txt
'''

5. Initialize the database:

'''bash
python database.py
'''

6. Start the Flask application:

'''bash
python app.py
'''
7. Open the application in a browser:

'''text
http://127.0.0.1:5000
'''