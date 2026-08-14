# Validation helpers for transaction forms.

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

ALLOWED_TRANSACTION_TYPES = {"income", "expense"}

def validate_transaction_form(form: Mapping[str, Any]) -> tuple[list[str], dict[str, Any]]:
    """
    Validate transaction form values. This function validates the
    transaction fields without saying anything to the database. 
    It can be used later by the transaction create and edit routes.
    
    Returns: A tuple containing a list of validation error messages 
    and a dictionary of cleaned values.
    """

    errors: list[str] = []
    cleaned_data: dict[str, Any] = {}

    # Validate amount.
    amount_text = str(form.get("amount", "")).strip()

    if not amount_text:
        errors.append("Amount is required.")
    else:
        try:
            amount = Decimal(amount_text)

            if not amount.is_finite() or amount <= 0:
                errors.append("Amount must be greater than zero.")
            else:
                cleaned_data["amount"] = float(amount)
        
        except InvalidOperation:
            errors.append("Amount must be a valid number.")
    
    # Validate transaction type.
    transaction_type = str(form.get("type", "")).strip().lower()

    if transaction_type not in ALLOWED_TRANSACTION_TYPES:
        errors.append("Type must be either income or expense.")
    else:
        cleaned_data["type"] = transaction_type
    
    # Validate category ID.
    category_id_text = str(form.get("category_id", "")).strip()

    if not category_id_text:
        errors.append("Category is required.")
    else:
        try:
            category_id = int(category_id_text)

            if category_id <= 0:
                errors.append("Please select a valid category.")
            else:
                cleaned_data["category_id"] = category_id
        
        except ValueError:
            errors.append("Please select a valid category.")
    
   # Validate transaction date.
    transaction_date_text = str(form.get("transaction_date", "")).strip()

    if not transaction_date_text:
        errors.append("Transaction date is required.")
    else:
        try:
            transaction_date = datetime.strptime(
                transaction_date_text,
                "%Y-%m-%d",
            ).date()

            cleaned_data["transaction_date"] = transaction_date.isoformat()

        except ValueError:
            errors.append("Transaction date must be a valid date.")
    
    # Description is optional.
    description = str(form.get("description", "")).strip()
    cleaned_data["description"] = description
    
    return errors, cleaned_data