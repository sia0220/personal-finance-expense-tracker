# Test Cases

## Authentication Tests

| Test ID | Feature | Test Steps | Expected Result | Status |
|---|---|---|---|---|
| TC-01 | Register | Enter valid email and password | Account is created | Not Started |
| TC-02 | Register | Enter duplicate email | Error message appears | Not Started |
| TC-03 | Login | Enter valid email and password | User goes to dashboard | Not Started |
| TC-04 | Login | Enter wrong password | Error message appears | Not Started |
| TC-05 | Logout | Click logout | Session ends and user returns to login | Not Started |

## Transaction Tests

| Test ID | Feature | Test Steps | Expected Result | Status |
|---|---|---|---|---|
| TC-06 | Add Transaction | Enter valid amount, date, category, type, description | Transaction saves to database | Not Started |
| TC-07 | Add Transaction | Enter negative amount | Error message appears | Not Started |
| TC-08 | Edit Transaction | Change amount or category | Transaction updates correctly | Not Started |
| TC-09 | Delete Transaction | Delete transaction | Transaction is removed | Not Started |
| TC-10 | Filter Transaction | Filter by category or date | Correct results display | Not Started |

## Budget and Alert Tests

| Test ID | Feature | Test Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| TC-11 | Create Budget | Enter category, month, and limit | Budget saves to database | Budget saved; limit of $0 rejected | Pass |
| TC-12 | Near Limit Alert | Spending reaches 80% of budget | Near-limit alert appears | Near-limit alert created at exactly 80% | Pass |
| TC-13 | Over Limit Alert | Spending reaches or passes 100% | Over-limit alert appears | Over-limit alert created at 100% and above | Pass |

## Report Tests 

| Test ID | Feature | Test Steps | Expected Result | Status |
|---|---|---|---|---|
| TC-14 | Spending by Category | Add transactions in different categories | Category totals display correctly | Not Started |
| TC-15 | Monthly Trend | Add transactions across months | Monthly summary displays correctly | Not Started |
