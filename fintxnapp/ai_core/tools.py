from fintxnapp.models import Transaction
from django.db.models import Sum, Avg
import calendar
from datetime import datetime, timedelta
from decimal import Decimal
from openai import OpenAI
from django.conf import settings
from django.utils.timezone import now
from langchain.tools import tool
from pydantic import BaseModel, Field
import json
from django.utils import timezone

from .prompts import (
    EXPLAIN_TERM_PROMPT,
    INVESTMENT_ADVISOR_PROMPT,
    BUDGET_PLANNER_PROMPT,
    BEHAVIOR_ANALYST_PROMPT,
    SMART_TIPS_PROMPT,
    PREDICTION_PROMPT,
    RATIONALIZER_PROMPT,
)

# Set OpenAI key (from .env via settings.py)
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Tool 1: Get User Spending Summary..........................................................................................................#
def get_user_spending_summary(category: str, month: str, year: str, user_id: int, transaction_type: str, *args, **kwargs):
    """
    Returns a detailed summary of spending or income in a category during a given month.
    Includes total amount, transaction count, and average transaction value.
    Example: category='Food', month='04', year='2025', user_id=1, transaction_type='credit' or 'debit'
    """
    try:
        month_number = int(month)
        qs = Transaction.objects.filter(
            user_id=user_id,
            transaction_type=transaction_type,
            category__name__iexact=category,
            date_time__year=int(year),
            date_time__month=month_number
        )
        total = qs.aggregate(total=Sum("amount"))["total"] or Decimal("0.0")
        count = qs.count()
        average = qs.aggregate(average=Avg("amount"))["average"] or Decimal("0.0") if count > 0 else Decimal("0.0")
        return {
            "category": category,
            "month": f"{year}-{month:02d}",
            "transaction_type": transaction_type,
            "total_amount": float(round(total, 2)),
            "transaction_count": count,
            "average_transaction_value": float(round(average, 2)),
        }
    except Exception as e:
        return {"error": str(e)}


# Tool 2: Suggest Investment Options (GPT-powered)..........................................................................................#
def get_investment_suggestions(amount: int, risk_level: str, user_id: int, *args, **kwargs):
    """
    Suggests a portfolio of low, medium, or high-risk investment options based on the user's
    monthly investment amount and risk preference, including rationale.

    This tool requires:
    - amount: Monthly investment amount in INR. Example: 5000
    - risk_level: Risk preference: 'low', 'medium', or 'high'

    Example usage:
    "I want to invest ₹5000 per month with low risk. What are my options and why?"
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-2025-04-14",
            messages=[
                {
                    "role": "system",
                    "content": INVESTMENT_ADVISOR_PROMPT
                },
                {
                    "role": "user",
                    "content": f"Suggest investment options for ₹{amount} monthly with {risk_level} risk, and explain the rationale for each suggestion."
                }
            ]
        )
        if response.choices:
            return response.choices[0].message.content.strip()
        else:
            return "No investment suggestions received from GPT."
    except Exception as e:
        return {"error": str(e)}


# Tool 3: Explain Financial Terms (GPT-powered)..............................................................................................#
def explain_financial_concept(term: str, user_id: int, *args, **kwargs):
    """
    Uses GPT to explain a financial term or concept in beginner-friendly language, including examples
    and potential implications for the user.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-2025-04-14",
            messages=[
                {
                    "role": "system",
                    "content": EXPLAIN_TERM_PROMPT
                },
                {
                    "role": "user",
                    "content": f"Explain the financial concept: {term}. Provide an example and explain why it might be important for me."
                }
            ]
        )
        if response.choices:
            return response.choices[0].message.content.strip()
        else:
            return "No explanation received from GPT."
    except Exception as e:
        return f"Error: {str(e)}"


# Tool 4: Predict User Spending............................................................................................................#
def predict_future_spending(user_id: int, *args, **kwargs):
    """
    Uses past 3 months' data to predict next month's spending across different categories using GPT,
    highlighting potential increases or decreases.
    """
    try:
        today = now().date()
        three_months_ago = today - timedelta(days=90)
        next_month_date = today.replace(day=1) + timedelta(days=32)
        next_month_str = next_month_date.strftime("%B")

        qs = Transaction.objects.filter(
            user_id=user_id,
            transaction_type="debit",
            date_time__date__gte=three_months_ago
        ).values("category__name").annotate(total=Sum("amount")).order_by('category__name')

        if not qs:
            return "Not enough transaction data to predict spending."

        category_spending = {row["category__name"]: float(row["total"]) for row in qs if row["category__name"]}

        response = client.chat.completions.create(
            model="gpt-4.1-2025-04-14",
            messages=[
                {
                    "role": "system",
                    "content": PREDICTION_PROMPT
                },
                {
                    "role": "user",
                    "content": f"Predict my spending for {next_month_str} based on my past 3 months of spending: {category_spending}. Highlight any categories where spending is likely to increase or decrease."
                }
            ]
        )

        if response.choices:
            return response.choices[0].message.content.strip()
        else:
            return "No spending predictions received from GPT."

    except Exception as e:
        return f"Error: {str(e)}"


# Tool 5: Give personalized smart tips (Saving and Financial)............................................................................#
def get_personalized_financial_tips(user_id: int, *args, **kwargs):
    """
    Uses GPT to generate actionable and personalized financial tips based on recent spending patterns,
    including saving opportunities and potential budget adjustments.
    """
    try:
        qs = Transaction.objects.filter(user_id=user_id).order_by("-date_time")[:100]

        if not qs:
            return "No recent transactions found for analysis."

        data = {}
        for txn in qs:
            cat = txn.category.name if txn.category else "Uncategorized"
            data.setdefault(cat, 0)
            data[cat] += float(txn.amount)

        print("📊 Sending data to GPT for tips:", json.dumps(data, indent=2), flush=True)

        response = client.chat.completions.create(
            model="gpt-4.1-2025-04-14",
            messages=[
                {
                    "role": "system",
                    "content": SMART_TIPS_PROMPT
                },
                {
                    "role": "user",
                    "content": f"Analyze my recent spending:\n{json.dumps(data, indent=2)}\n\nProvide 3-5 personalized and actionable financial tips, including potential saving opportunities and budget adjustments."
                }
            ]
        )

        if response.choices:
            return response.choices[0].message.content.strip()
        else:
            return "No personalized financial tips received from GPT."

    except Exception as e:
        return f"Error: {str(e)}"


# Tool 6: Evaluate a purchase against user savings, habits, and budget.....................................................................#
def evaluate_proposed_purchase(item: str, cost: float, user_id: int, *args, **kwargs):
    """
    Uses GPT to evaluate whether a proposed purchase is financially smart.
    Compares cost with savings, spending habits, and goals, providing a recommendation with reasoning.
    """
    try:
        recent_txns = Transaction.objects.filter(user_id=user_id).order_by("-date_time")[:50]
        total_spent = sum(float(t.amount) for t in recent_txns if t.transaction_type == "debit")
        total_credited = sum(float(t.amount) for t in recent_txns if t.transaction_type == "credit")
        savings_estimate = max(0, total_credited - total_spent)

        context = {
            "item": item,
            "cost": cost,
            "recent_spending": round(total_spent, 2),
            "recent_income": round(total_credited, 2),
            "estimated_savings": round(savings_estimate, 2)
        }

        response = client.chat.completions.create(
            model="gpt-4.1-2025-04-14",
            messages=[
                {
                    "role": "system",
                    "content": RATIONALIZER_PROMPT
                },
                {
                    "role": "user",
                    "content": f"Should I buy '{item}' for ₹{cost}? Here's my recent financial context: {context}. Please provide a recommendation (yes/no) and explain your reasoning based on my savings and spending habits."
                }
            ]
        )

        if response.choices:
            return response.choices[0].message.content.strip()
        else:
            return "No purchase evaluation received from GPT."

    except Exception as e:
        return f"Error: {str(e)}"


# Tool 7: Auto-suggest a monthly budget based on past category-wise spending...............................................................#
def suggest_monthly_budget(user_id: int, *args, **kwargs):
    """
    Analyzes past spending and uses GPT to generate a personalized monthly budget plan with
    recommended spending limits for various categories and an overall savings target.
    """
    try:
        qs = Transaction.objects.filter(user_id=user_id, transaction_type="debit").order_by("-date_time")[:100]
        if not qs:
            return "No transaction data available to build a budget."

        category_totals = {}
        for txn in qs:
            cat = txn.category.name if txn.category else "Uncategorized"
            category_totals.setdefault(cat, 0)
            category_totals[cat] += float(txn.amount)

        response = client.chat.completions.create(
            model="gpt-4.1-2025-04-14",
            messages=[
                {
                    "role": "system",
                    "content": BUDGET_PLANNER_PROMPT
                },
                {
                    "role": "user",
                    "content": f"Analyze my past category-wise spending: {category_totals}. Suggest a detailed monthly budget plan with recommended spending limits for each category and an overall savings target."
                }
            ]
        )

        if response.choices:
            return response.choices[0].message.content.strip()
        else:
            return "No budget suggestions received from GPT."

    except Exception as e:
        return f"Error: {str(e)}"


# Tool 8: Summarizes user’s spending behavior, categories, trends and explains user's financial habits......................................#
def summarize_financial_behavior(user_id: int, *args, **kwargs):
    """
    Uses GPT to analyze user's recent transactions and describe behavior patterns,
    spending habits, and notable trends.
    """
    try:
        txns = Transaction.objects.filter(user_id=user_id).order_by("-date_time")[:100]

        if not txns:
            return "No transaction data available to summarize."

        behavior_data = {}
        for txn in txns:
            cat = txn.category.name if txn.category else "Uncategorized"
            behavior_data.setdefault(cat, 0)
            behavior_data[cat] += float(txn.amount)

        response = client.chat.completions.create(
            model="gpt-4.1-2025-04-14",
            messages=[
                {
                    "role": "system",
                    "content": BEHAVIOR_ANALYST_PROMPT
                },
                {
                    "role": "user",
                    "content": f"Analyze my recent category spending: {behavior_data}. Provide a summary of my spending behavior, identify key spending categories, any notable trends (increasing/decreasing spending), and explain my overall financial habits."
                }
            ]
        )

        if response.choices:
            return response.choices[0].message.content.strip()
        else:
            return "No financial behavior summary received from GPT."

    except Exception as e:
        return f"Error: {str(e)}"


# Tool 9: Returns a simple score (0–100) based on income vs expenses and savings ratio.....................................................#
def calculate_financial_health_score(month: str, year: str, user_id: int, *args, **kwargs):
    """
    Calculates a financial health score (0-100) based on income, expenses, and savings ratio
    for a specific month, along with a breakdown of contributing factors and areas for improvement.
    """
    try:
        month_number = int(month)
        recent_txns = Transaction.objects.filter(
            user_id=user_id,
            date_time__year=int(year),
            date_time__month=month_number
        ).order_by("-date_time")

        print(f"📊 calculate_financial_health_score | month: {month} | year: {year} | user_id: {user_id}", flush=True)

        if not recent_txns:
            return {"score": 0, "message": "No data to calculate financial health score for this month."}

        income = sum(float(t.amount) for t in recent_txns if t.transaction_type == "credit")
        expense = sum(float(t.amount) for t in recent_txns if t.transaction_type == "debit")
        savings = max(0, income - expense)

        score = int(min(100, (savings / income) * 100)) if income > 0 else 0

        interpretation = ""
        if score >= 75:
            interpretation = "Excellent financial health. You have a strong savings rate and good balance between income and expenses."
        elif score >= 50:
            interpretation = "Good financial health. You are saving a reasonable portion of your income, but there's room for improvement."
        elif score >= 25:
            interpretation = "Fair financial health. Your savings rate is low, and you might need to review your expenses to improve your financial position."
        else:
            interpretation = "Needs significant improvement. Your expenses are high relative to your income, resulting in minimal or no savings. Consider creating a budget and identifying areas to reduce spending."

        contributing_factors = {
            "savings_rate": f"{round((savings / income) * 100, 2)}%" if income > 0 else "N/A",
            "income": round(income, 2),
            "expenses": round(expense, 2)
        }

        areas_for_improvement = []
        if savings / income < 0.1:
            areas_for_improvement.append("Consider increasing your savings rate by identifying non-essential expenses.")
        if expense / income > 0.8:
            areas_for_improvement.append("Review your spending habits to find opportunities to reduce expenses.")
        if income == 0 and expense > 0:
            areas_for_improvement.append("Focus on generating income streams to improve your financial health.")

        return {
            "score": score,
            "status": interpretation,
            "contributing_factors": contributing_factors,
            "areas_for_improvement": areas_for_improvement
        }

    except Exception as e:
        return {"score": 0, "error": str(e)}
    

# Tool 10: Returns account balance details .....................................................#def get_account_balance_details(user_id: int, detail: str = "current", start_date: str = None, end_date: str = None, transaction_type: str = None, *args, **kwargs):
def get_account_balance_details(user_id: int, detail: str = "current", start_date: str = None, end_date: str = None, transaction_type: str = None, *args, **kwargs):
    """
    Retrieves account balance details for a specific user, with optional filtering by
    date range and transaction type, similar to the UserBalanceView.

    Args:
        user_id (int): The ID of the user.
        detail (str, optional): The type of balance detail to retrieve.
            Options are "current", "month_balance", "month_expenses". Defaults to "current".
        start_date (str, optional): Filter transactions on or after this date (YYYY-MM-DD). Defaults to None.
        end_date (str, optional): Filter transactions on or before this date (YYYY-MM-DD). Defaults to None.
        transaction_type (str, optional): Filter by transaction type ('credit' or 'debit'). Defaults to None.

    Returns:
        str: A string describing the requested balance information.
            Returns an error message if no transactions are found or if an invalid detail is requested.
    """
    try:
        transactions = Transaction.objects.filter(user_id=user_id)

        if not transactions.exists():
            return "No transaction data available for this user."

        if detail == "current":
            total_credit = transactions.filter(transaction_type='credit').aggregate(Sum('amount'))['amount__sum'] or 0
            total_debit = transactions.filter(transaction_type='debit').aggregate(Sum('amount'))['amount__sum'] or 0
            current_balance = total_credit - total_debit
            return f"Your current account balance is: ₹{current_balance:.2f}"
        elif detail == "month_balance":
            if start_date and end_date:
                try:
                    start_of_month = datetime.strptime(start_date, '%Y-%m-%d').date()
                    end_of_month = datetime.strptime(end_date, '%Y-%m-%d').date()
                except ValueError:
                    return "Invalid date format. Please use YYYY-MM-DD."
            else:
                now = timezone.now()
                start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).date()
                end_of_month = now.replace(day=calendar.monthrange(now.year, now.month)[1], hour=23, minute=59, second=59, microsecond=999999).date()

            monthly_credit = transactions.filter(transaction_type='credit', date_time__gte=start_of_month, date_time__lte=end_of_month).aggregate(Sum('amount'))['amount__sum'] or 0
            monthly_debit = transactions.filter(transaction_type='debit', date_time__gte=start_of_month, date_time__lte=end_of_month).aggregate(Sum('amount'))['amount__sum'] or 0
            monthly_balance_change = monthly_credit - monthly_debit
            return f"Your balance change from {start_of_month} to {end_of_month} is: ₹{monthly_balance_change:.2f} (Credits: ₹{monthly_credit:.2f}, Debits: ₹{monthly_debit:.2f})"
        elif detail == "month_expenses":
            if start_date and end_date:
                try:
                    start_of_month = datetime.strptime(start_date, '%Y-%m-%d').date()
                    end_of_month = datetime.strptime(end_date, '%Y-%m-%d').date()
                except ValueError:
                    return "Invalid date format. Please use YYYY-MM-DD."
            else:
                now = timezone.now()
                start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).date()
                end_of_month = now.replace(day=calendar.monthrange(now.year, now.month)[1], hour=23, minute=59, second=59, microsecond=999999).date()
            monthly_expenses = transactions.filter(transaction_type='debit', date_time__gte=start_of_month, date_time__lte=end_of_month).aggregate(Sum('amount'))['amount__sum'] or 0
            return f"Your total expenses from {start_of_month} to {end_of_month} are: ₹{monthly_expenses:.2f}"
        else:
            return "Invalid balance detail requested. Please specify 'current', 'month_balance', or 'month_expenses'."

    except Exception as e:
        return f"Error retrieving balance details: {str(e)}"