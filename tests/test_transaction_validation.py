# Tests for transaction form validation

import pytest
from transaction_validation import validate_transaction_form

def valid_transaction_form() -> dict[str, str]:
    # Return valid transaction form data for testing.

    return {
        "amount": "25.50",
        "type": "expense",
        "category_id": "1",
        "transaction_date": "2026-07-28",
        "description": "Groceries"
    }

def test_valid_transaction_form() -> None:
    form = valid_transaction_form()

    errors, cleaned_data = validate_transaction_form(form)

    assert errors == []
    assert cleaned_data["amount"] == 25.50
    assert cleaned_data["type"] == "expense"
    assert cleaned_data["category_id"] == 1
    assert cleaned_data["transaction_date"] == "2026-07-28"
    assert cleaned_data["description"] == "Groceries"

def test_amount_is_required() -> None:
    form = valid_transaction_form()
    form["amount"] = ""

    errors, _ = validate_transaction_form(form)

    assert "Amount is required." in errors

@pytest.mark.parametrize("amount", ["0", "-10.00"])
def test_amount_must_be_greater_than_zero(amount: str) -> None:
    form = valid_transaction_form()
    form["amount"] = amount
    
    errors, _ = validate_transaction_form(form)

    assert "Amount must be greater than zero." in errors

def test_amount_must_be_a_number() -> None:
    form = valid_transaction_form()
    form["amount"] = "abc"

    errors, _ = validate_transaction_form(form)

    assert "Amount must be a valid number." in errors

def test_type_must_be_valid() -> None:
    form = valid_transaction_form()
    form["type"] = "other"

    errors, _ = validate_transaction_form(form)

    assert "Type must be either income or expense." in errors

def test_category_is_required() -> None:
    form = valid_transaction_form()
    form["category_id"] = ""

    errors, _ = validate_transaction_form(form)

    assert "Category is required." in errors

def test_category_id_must_be_valid() -> None:
    form = valid_transaction_form()
    form["category_id"] = "abc"

    errors, _ = validate_transaction_form(form)

    assert "Please select a valid category." in errors


def test_transaction_date_is_required() -> None:
    form = valid_transaction_form()
    form["transaction_date"] = ""

    errors, _ = validate_transaction_form(form)

    assert "Transaction date is required." in errors


def test_transaction_date_must_be_valid() -> None:
    form = valid_transaction_form()
    form["transaction_date"] = "not-a-date"

    errors, _ = validate_transaction_form(form)

    assert "Transaction date must be a valid date." in errors


def test_description_is_optional() -> None:
    form = valid_transaction_form()
    form["description"] = ""

    errors, cleaned_data = validate_transaction_form(form)

    assert errors == []
    assert cleaned_data["description"] == ""


def test_description_spaces_are_removed() -> None:
    form = valid_transaction_form()
    form["description"] = "  Gas station  "

    errors, cleaned_data = validate_transaction_form(form)

    assert errors == []
    assert cleaned_data["description"] == "Gas station"




