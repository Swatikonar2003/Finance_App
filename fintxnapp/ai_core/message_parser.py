from openai import OpenAI
from django.conf import settings
from fintxnapp.models import Category, Transaction, Tag
from decimal import Decimal         # Decimal is crucial for handling financial amounts accurately,
import json

# Set OpenAI key (from .env via settings.py)
client = OpenAI(api_key=settings.OPENAI_API_KEY)

def parse_and_save_transaction_from_sms(message, user):
    """
    Parses a raw SMS-style message using GPT, extracts structured info,
    and saves it as a Transaction for the given user.
    """
    system_prompt = """
    You are a smart financial assistant. Extract accurate structured transaction data from SMS-like messages.

    Respond ONLY in valid JSON format like:

    {
    "amount": 500.0,
    "transaction_type": "credit",
    "category": "Shopping",
    "tags": ["amazon", "online", "shopping"],
    "is_recurring": false
    }

    Guidelines:
    - category: general label like "Grocery", "Utilities", "Salary", "Dining", "Recharge", "Bills"
    - tags: short, lowercase terms describing the transaction (max 3), like ["paytm", "groceries", "electricity"]
    - is_recurring: true if the SMS suggests a repeated transaction (e.g., rent, EMI), else false

    Only respond with ONLY valid JSON. No explanation or commentary.
    """

    user_prompt = f"""
    Extract the transaction from the message:
    "{message}" 
    If it's not valid, reply: "INVALID"
    """

    # Call GPT
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-2025-04-14",
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()}
            ]
        )
        content = response.choices[0].message.content.strip()
    except Exception as e:
        raise ValueError(f"OpenAI Error: {str(e)}")

    # Handle invalid response
    if "INVALID" in content.upper():
        raise ValueError("Sorry, we couldn't understand this message. Please try a different one.")

    try:
        data = json.loads(content)
    except Exception:
        raise ValueError("Invalid AI response format.")

    # Validate extracted data
    try:
        amount = Decimal(str(data.get("amount", 0)))
        if amount <= 0:
            raise ValueError("Amount must be greater than 0.")
    except:
        raise ValueError("Invalid or missing amount.")

    transaction_type = data.get("transaction_type", "").lower()
    if transaction_type not in ["credit", "debit"]:
        raise ValueError("Invalid transaction type.")

    category_name = data.get("category", "").strip() or "Misc"
    tags = data.get("tags", [])
    is_recurring = data.get("is_recurring", False)

    # --- Save to DB ---
    category, _ = Category.objects.get_or_create(name=category_name, created_by=user)

    txn = Transaction.objects.create(
        user=user,
        amount=amount,
        transaction_type=transaction_type,
        category=category,
        is_recurring=is_recurring,  
    )

    tag_objs = []
    for tag in tags:
        t, _ = Tag.objects.get_or_create(name=tag.strip(), created_by=user)     # The retrieved or created Tag object is assigned to t.
        tag_objs.append(t)
    #This line sets the many-to-many relationship between the newly created transaction and the Tag objects in the tag_objs list.
    txn.tags.set(tag_objs)

    return txn