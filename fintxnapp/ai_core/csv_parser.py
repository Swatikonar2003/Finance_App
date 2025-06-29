from openai import OpenAI
import csv     #mports the csv module for working with CSV 
import io
import json
from decimal import Decimal
from django.conf import settings
from fintxnapp.models import Transaction, Category, Tag


# Set OpenAI key (from .env via settings.py)
client = OpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """
You are a smart financial assistant. Extract transaction details from SMS-like messages.

Respond only in valid JSON like:
{
  "amount": 750.0,
  "transaction_type": "debit",
  "category": "Grocery",
  "tags": ["groceries", "vegetables"],
  "is_recurring": false
}

If invalid, respond with: {"error": "INVALID"}
""" 

# takes a single SMS message (as a string) and is expected to return a dictionary containing the extracted transaction details.
def extract_transaction_from_message(message: str) -> dict:
    """
    Calls OpenAI API to parse a single SMS message into structured format.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-2025-04-14",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f'Extract from: "{message}"'}
            ]
        )
        content = response.choices[0].message.content.strip()
        return json.loads(content)
    except Exception as e:
        return {"error": str(e)}

def extract_sms_column(row):
    """
    Returns the column that is most likely to be the SMS message.
    Assumes SMS will be the longest column with actual text.
    """
    return max(row, key=lambda col: len(col.strip()) if col else 0, default="").strip()

def process_csv_and_extract(file, user, save_to_db=False):
    """
    Takes uploaded CSV, extracts structured transaction info via OpenAI,
    saves to DB if needed, and returns insights + raw results.
    """
    # Reads the content of the uploaded file and decodes it from UTF-8 encoding into a string.
    decoded = file.read().decode('utf-8')
    # io.StringIO(decoded) treats the decoded string as an in-memory text file. 
    reader = csv.reader(io.StringIO(decoded))  
    reader = list(reader)
    if reader and any("sms" in col.lower() or "message" in col.lower() for col in reader[0]):
        reader = reader[1:]  # skip header 
    results = []

    # --- For insights aggregation --- #
    total_credit = Decimal('0.0')
    total_debit = Decimal('0.0')
    transaction_amounts = []
    category_counts = {}
    tag_counts = {}
    recurring_count = 0
    max_txn = {"amount": Decimal("0"), "category": "", "type": ""}

    # Initialize counters to track the number of successfully parsed and failed messages.
    success_count = 0
    failure_count = 0

    for row in reader:
        if not row:
            continue
        message = extract_sms_column(row)
        if not message:
            continue
        parsed = extract_transaction_from_message(message)

        if "error" in parsed:
            failure_count += 1
            # results list containing the original message and the error message from the parsing attempt.
            results.append({"message": message, "error": parsed["error"]})
            continue
        success_count += 1

        try:
            amount = Decimal(str(parsed["amount"]))
            txn_type = parsed["transaction_type"]
            category_name = parsed["category"]
            tag_names = parsed.get("tags", [])
            is_recurring = parsed.get("is_recurring", False)

            # --- Update insights --- #
            # Adds the amount to total_credit or total_debit based on the txn_type.
            if txn_type == "credit":
                total_credit += amount
            else: 
                total_debit += amount
            transaction_amounts.append(amount)

            if amount > max_txn["amount"]:
                max_txn = {
                    "amount": amount,
                    "category": category_name,
                    "type": txn_type
                }

            category_counts[category_name] = category_counts.get(category_name, 0) + 1
            for tag in tag_names:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

            if is_recurring:
                recurring_count += 1

            # Save if requested
            if save_to_db:
                category, _ = Category.objects.get_or_create(name=category_name, created_by=user)
                txn = Transaction.objects.create(
                    user=user,
                    amount=amount,
                    transaction_type=txn_type,
                    category=category,
                    is_recurring=is_recurring
                )
                tag_objs = []
                for tag in tag_names:
                    t, _ = Tag.objects.get_or_create(name=tag.strip(), created_by=user)
                    tag_objs.append(t)
                txn.tags.set(tag_objs)
                results.append({"message": message, "status": "saved", "id": txn.id})
            else:
                results.append({"message": message, "parsed": parsed})

        except Exception as e:
            # Increments the failure_count as an error occurred during the saving process.
            failure_count += 1
            results.append({"message": message, "error": str(e)})

    # --- Compute average transaction --- #
    avg_transaction_amount = (sum(transaction_amounts) / len(transaction_amounts)) if transaction_amounts else 0

    # --- Sort & pick top 3 categories and tags --- #
    # Sorts the category_counts dictionary items (key-value pairs) in descending order based on the count (the value, x[1]) and takes the first 3 elements (top 3).
    top_categories = sorted(category_counts.items(), key=lambda x: -x[1])[:3]
    top_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:3]

    # --- Final response ---
    return {
        "message": "CSV processed successfully.",
        "summary": {
            "total_messages": success_count + failure_count,
            "parsed_successfully": success_count,
            "failed": failure_count,
            "total_credit": float(total_credit),
            "total_debit": float(total_debit),
            "average_transaction_amount": float(round(avg_transaction_amount, 2)),   # average transaction amount (rounded to 2 decimal places and converted to float).
            "top_categories": [cat for cat, _ in top_categories],
            "top_tags": [tag for tag, _ in top_tags],
            "max_transaction": {
                "amount": float(max_txn["amount"]),
                "category": max_txn["category"],
                "type": max_txn["type"]
            },
            "recurring_count": recurring_count
        },
        "results": results
    }