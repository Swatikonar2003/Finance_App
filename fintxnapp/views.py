
# Import necessary modules and classes for API views and functionality
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.generics import RetrieveUpdateDestroyAPIView

from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Avg
from django.db.models.functions import TruncMonth, TruncDay, TruncWeek  
from collections import defaultdict
from .utils import (
    generate_monthly_report_pdf ,
    send_monthly_report_email
)
from django.http import FileResponse

from calendar import monthrange   #returns information about a given month, including the number of days in that month.
from datetime import datetime, timedelta
import base64
from django.core.cache import cache

from .models import Tag, Category, Transaction, ChatHistory
from .serializers import (
    TagSerializer,
    CategorySerializer,
    TransactionSerializer, 
    MessageInputSerializer, 
    CSVUploadSerializer
)
from .ai_core.message_parser import parse_and_save_transaction_from_sms
from .ai_core.agent import run_chatbot
from .tasks import process_csv_file_task


from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

# Get the user model dynamically to support custom user models
User = get_user_model()


# Tag List View
class TagListView(APIView):
    """
    API view to list all tags created by the authenticated user.
    Only tags created by the authenticated user are returned.
    """
    permission_classes = [IsAuthenticated]  # Only authenticated users can access this view

    @swagger_auto_schema(
        operation_summary="List all tags for the authenticated user",
        responses={200: TagSerializer(many=True)}  # Return a list of tags
    )
    
    def get(self, request):
        """
        Retrieve all tags for the authenticated user.
        """
        user = request.user
        tags = Tag.objects.filter(created_by=user)  # Filter tags by the current user
        serializer = TagSerializer(tags, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# Category View
class CategoryView(APIView):
    """
    This view allows the authenticated user to manage their expense categories.
    Users can fetch all categories or create a new category.
    """
    permission_classes = [IsAuthenticated]  # Only authenticated users can access this view

    @swagger_auto_schema(
        operation_summary="List all categories",
        responses={200: CategorySerializer(many=True)},
    )
    def get(self, request):
        """
        Retrieve all categories associated with the authenticated user.
        Categories are filtered by the `created_by` field.
        """
        categories = Category.objects.filter(created_by=request.user)  # Fetch categories for the user
        serializer = CategorySerializer(categories, many=True)  # Serialize the data
        return Response(serializer.data, status=status.HTTP_200_OK)  # Return serialized data with HTTP 200

    @swagger_auto_schema(
        operation_summary="Create a new category",
        request_body=CategorySerializer,
        responses={201: CategorySerializer, 400: "Validation Error"},
    )
    def post(self, request):
        """
        Create a new expense category for the authenticated user.
        The `created_by` field is automatically set to the current user.
        """
        
        serializer = CategorySerializer(data=request.data)  # Deserialize and validate the data
        if serializer.is_valid():
            serializer.save(created_by=request.user)  # Save the new category if valid
            return Response(serializer.data, status=status.HTTP_201_CREATED)  # Return created category data
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)  # Return errors if invalid


class TransactionView(APIView): 
    """
    This view allows the authenticated user to manage their transactions.
    Users can fetch all transactions or create a new transaction.
    """
    permission_classes = [IsAuthenticated]  # Only authenticated users can access this view

    @swagger_auto_schema(
        operation_summary="List all transactions",
        responses={200: TransactionSerializer(many=True)},
    )
    def get(self, request):
        """
        Retrieve all transactions associated with the authenticated user.
        Transactions are filtered by the `user` field.
        """
        user = request.user
        transactions = Transaction.objects.filter(user=user)  # Fetch transactions for the user

        # Date filters
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        if start_date:
            transactions = transactions.filter(date_time__date__gte=start_date)
        if end_date:
            transactions = transactions.filter(date_time__date__lte=end_date)

        # Transaction type filter (credit / debit)
        txn_type = request.query_params.get("transaction_type")
        if txn_type in ["credit", "debit"]:
            transactions = transactions.filter(transaction_type=txn_type)

        # Amount filters
        min_amount = request.query_params.get("min_amount")
        max_amount = request.query_params.get("max_amount")
        if min_amount:
            transactions = transactions.filter(amount__gte=min_amount)
        if max_amount:
            transactions = transactions.filter(amount__lte=max_amount)
        
        # Category filter
        category = request.query_params.get("category")
        if category:
            transactions = transactions.filter(category__name__icontains=category)

        # Recurring filter
        is_recurring = request.query_params.get("is_recurring")
        if is_recurring == "true":
            transactions = transactions.filter(is_recurring=True)
        elif is_recurring == "false":
            transactions = transactions.filter(is_recurring=False)

        # Tag filter (exact match of tag name)
        tag_name = request.query_params.get("tags")
        if tag_name:
            transactions = transactions.filter(tags__name__iexact=tag_name)

        # ✅ Sort by latest
        transactions = transactions.order_by('-date_time')

        serializer = TransactionSerializer(transactions, many=True)  # Serialize the data
        return Response(serializer.data, status=status.HTTP_200_OK)  # Return serialized data with HTTP 200

    @swagger_auto_schema(
        operation_summary="Create a new transaction",
        request_body=TransactionSerializer,
        responses={201: TransactionSerializer, 400: "Validation Error"},
    )
    def post(self, request):
        """
        Create a new transaction for the authenticated user.
        The `user` field is automatically set to the current user.
        """
        serializer = TransactionSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(user=request.user)   # Save the new transaction if valid
            return Response(serializer.data, status=status.HTTP_201_CREATED)  # Return created transaction data
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)  # Return errors if invalid
    
class TransactionDetailView(RetrieveUpdateDestroyAPIView):
    """
    API view to handle a single transaction instance.
    Supports:
    - GET (retrieve single transaction)
    - PUT (update transaction)
    - DELETE (delete transaction)

    Only accessible to the authenticated user who owns the transaction.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = TransactionSerializer
 
    def get_queryset(self):
        """
        Filter transactions to only those owned by the requesting user.
        Prevents accessing or editing others' transactions.
        """
        return Transaction.objects.filter(user=self.request.user)


class UserBalanceView(APIView):
    """
    This view calculates and returns the authenticated user's current balance.
    The balance is computed based on all credit and debit transactions.
    """
    permission_classes = [IsAuthenticated]  # Only authenticated users can access this view

    @swagger_auto_schema(
        operation_summary="Get user balance",
        responses={
            200: openapi.Response(
                description="User balance",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'balance': openapi.Schema(type=openapi.TYPE_NUMBER, description="User's current balance"),
                    },
                ),
            ),
        },
    )
    def get(self, request):
        """
        Calculate and return the user's balance based on their transactions.
        Credits add to the balance, while debits subtract from it.
        """
        user = request.user  # Get the authenticated user
        transactions = Transaction.objects.filter(user=user)  # Fetch all transactions for the user

        # Date filters
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        if start_date:
            transactions = transactions.filter(date_time__date__gte=start_date)
        if end_date:
            transactions = transactions.filter(date_time__date__lte=end_date)

        # Transaction type filter (credit / debit)
        txn_type = request.query_params.get("transaction_type")
        if txn_type in ["credit", "debit"]:
            transactions = transactions.filter(transaction_type=txn_type)

        balance = sum(
            transaction.amount if transaction.transaction_type == 'credit' else -transaction.amount
            for transaction in transactions
        )  # Calculate the balance by summing credits and debits
        return Response({"balance": balance}, status=status.HTTP_200_OK)  # Return the calculated balance


class TransactionCategoryPercentageView(APIView):
    """
    API View to calculate and return transaction data categorized by 
    categories along with their respective percentages of the total amount.

    This view is used to provide data for visualizing a pie chart on the frontend.
    It calculates the total transaction amount for each category and computes 
    their percentage contribution relative to the overall total.
    """
    permission_classes = [IsAuthenticated]  # Ensures only authenticated users can access this endpoint

    @swagger_auto_schema(
        operation_summary="Get transaction data by category with percentages",
        responses={
            200: openapi.Response(
                description="Category data with percentage",
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,  # The response is a list of objects
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'category': openapi.Schema(
                                type=openapi.TYPE_STRING, 
                                description="Category name"
                            ),
                            'total_amount': openapi.Schema(
                                type=openapi.TYPE_NUMBER, 
                                description="Total amount in the category"
                            ),
                            'percentage': openapi.Schema(
                                type=openapi.TYPE_NUMBER, 
                                description="Percentage of total transactions"
                            ),
                        },
                    ),
                ),
            ),
            404: "No transactions found for the user",  # Response when there are no transactions
        },
    )
    def get(self, request):
        """
        Get the percentage of transactions for each category for the authenticated user.
        
        Returns:
            - A list of objects containing:
                - `category`: Name of the category.
                - `total_amount`: Total transaction amount in the category.
                - `percentage`: Percentage contribution of the category to the overall transactions.
            - 404 if the user has no transactions.
        """
        user = request.user  # Get the currently authenticated user

        # Query to calculate total transaction amount per category for the user
        category_totals = (
            Transaction.objects.filter(user=user)  # Filter transactions by the authenticated user
            .values('category__name')  # Group by category name
            .annotate(total_amount=Sum('amount'))  # Sum up the amount for each category
        )

        # Calculate the overall total transaction amount
        overall_total = sum(item['total_amount'] for item in category_totals)

        # If no transactions are found, return an error response
        if overall_total == 0:
            return Response({"error": "No transactions found for the user"}, status=status.HTTP_404_NOT_FOUND)

        # Create the result list with category name, total amount, and percentage
        result = [
            {
                "category": item['category__name'],
                "total_amount": item['total_amount'],
                "percentage": round((item['total_amount'] / overall_total) * 100, 2),  # Calculate percentage
            }
            for item in category_totals
        ]

        # Return the result as a response
        return Response(result, status=status.HTTP_200_OK)
    

class MonthlySummaryView(APIView):
    """
    API View to return monthly financial summaries.
    Includes:
    - total credit, total debit, balance
    - transaction count, average amount
    - savings rate
    - top 3 categories and tags
    - start and end dates of the month
    - net change from the previous month
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Group transactions by user & truncate to month
        txns = Transaction.objects.filter(user=user).annotate(month=TruncMonth('date_time'))

        monthly_data = defaultdict(list)

        # Group transactions into month buckets
        for txn in txns:
            month_key = txn.month.strftime('%Y-%m')
            monthly_data[month_key].append(txn)

        result = []
        previous_balance = 0  # Track for net change month-to-month

        for month in sorted(monthly_data.keys()):
            data = monthly_data[month]
            total_credit = sum(tx.amount for tx in data if tx.transaction_type == 'credit')
            total_debit = sum(tx.amount for tx in data if tx.transaction_type == 'debit')
            balance = total_credit - total_debit
            count = len(data)
            avg = round((total_credit + total_debit) / count, 2) if count else 0
            savings_rate = round(((total_credit - total_debit) / total_credit * 100), 2) if total_credit > 0 else 0
            net_change = round(balance - previous_balance, 2)

            # Count categories & tags
            category_totals = defaultdict(float)
            tag_counts = defaultdict(int)
            for tx in data:
                if tx.category:
                    category_totals[tx.category.name] += float(tx.amount)
                for tag in tx.tags.all():
                    tag_counts[tag.name] += 1

            # Sort top 3
            top_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:3]    #Sorts this list of tuples based on the second element of each tuple (the total amount) in descending order
            top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:3]

            # Get month start and end date
            year, month_num = map(int, month.split("-"))
            start_date = f"{year}-{month_num:02d}-01"
            last_day = monthrange(year, month_num)[1]
            end_date = f"{year}-{month_num:02d}-{last_day:02d}"

            result.append({
                "month": month,
                "total_credit": round(total_credit, 2),
                "total_debit": round(total_debit, 2),
                "balance": round(balance, 2),
                "transaction_count": count,
                "avg_amount": avg,
                "savings_rate": savings_rate,
                "top_categories": [x[0] for x in top_categories],
                "top_tags": [x[0] for x in top_tags],
                "start_date": start_date,
                "end_date": end_date,
                "net_change_from_last": net_change
            })

            previous_balance = balance  # Store for next loop

        return Response(result, status=status.HTTP_200_OK)


class TopCategoriesView(APIView):
    """
    Returns the top N spending categories by total debit amount.
    Optional filters:
    - ?month=YYYY-MM
    - ?top_n=5
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        top_n = int(request.query_params.get("top_n", 5))
        month_str = request.query_params.get("month")

        transactions = Transaction.objects.filter(user=user, transaction_type='debit')

        # Filter by month if provided
        if month_str:
            try:
                month_date = datetime.strptime(month_str, "%Y-%m")
                transactions = transactions.filter(date_time__year=month_date.year,
                                                   date_time__month=month_date.month)
            except ValueError:
                return Response(
                    {"error": "Invalid month format. Use YYYY-MM."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Group by category and sum debit
        category_totals = (
            transactions.values('category__name')
            .annotate(total_spent=Sum('amount'))
            .order_by('-total_spent')[:top_n]
        )

        result = [
            {"category": entry['category__name'], "total_spent": round(entry['total_spent'], 2)}
            for entry in category_totals if entry['category__name']
        ]

        return Response(result, status=status.HTTP_200_OK)
    

class TopTransactionsView(APIView):
    """
    Returns top N transactions sorted by amount.
    Optional filters:
    - ?transaction_type=credit/debit
    - ?month=YYYY-MM
    - ?top_n=5 (default)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        txns = Transaction.objects.filter(user=user)

        # Query parameters
        txn_type = request.query_params.get("transaction_type")
        month_str = request.query_params.get("month")
        top_n = int(request.query_params.get("top_n", 5))

        if txn_type in ['credit', 'debit']:
            txns = txns.filter(transaction_type=txn_type)

        if month_str:
            try:
                month_dt = datetime.strptime(month_str, "%Y-%m")
                txns = txns.filter(date_time__year=month_dt.year, date_time__month=month_dt.month)
            except ValueError:
                return Response(
                    {"error": "Invalid month format. Use YYYY-MM."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        txns = txns.order_by('-amount')[:top_n]

        # Custom serialization
        data = []
        for txn in txns:
            data.append({
                "id": txn.id,
                "amount": float(txn.amount),
                "transaction_type": txn.transaction_type,
                "category": txn.category.name if txn.category else None,
                "date": txn.date_time.date().isoformat(),
                "tags": [tag.name for tag in txn.tags.all()]
            })

        return Response(data, status=status.HTTP_200_OK)


class SpendingTrendView(APIView):
    """
    Returns credit and debit totals grouped by day or week.
    Supports:
    - mode=daily (default)
    - mode=weekly
    - optional month filter (YYYY-MM)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        mode = request.query_params.get("mode", "daily")
        month_str = request.query_params.get("month")

        txns = Transaction.objects.filter(user=user)

        # Optional month filter
        if month_str:
            try:
                month_dt = datetime.strptime(month_str, "%Y-%m")
                txns = txns.filter(date_time__year=month_dt.year,
                                   date_time__month=month_dt.month)
            except ValueError:
                return Response(
                    {"error": "Invalid month format. Use YYYY-MM."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Group by day or week
        if mode == "weekly":
            txns = txns.annotate(period=TruncWeek("date_time"))
        else:
            txns = txns.annotate(period=TruncDay("date_time"))

        # Aggregate credit and debit totals
        grouped = txns.values("period", "transaction_type").annotate(total=Sum("amount"))

        # Format response
        trend_data = {}
        for entry in grouped:
            period = entry["period"].date().isoformat()
            t_type = entry["transaction_type"]
            amount = float(entry["total"])

            if period not in trend_data:
                # If the period is not yet a key, a new entry is created in trend_data with the period as the key and a dictionary containing initial credit and debit values set to 0.0.
                trend_data[period] = {"credit": 0.0, "debit": 0.0} 
            #updates the credit or debit value for the current period based on the t_type
            trend_data[period][t_type] += amount

        # Final result list
        result = [
            {"date": key, "credit": round(value["credit"], 2), "debit": round(value["debit"], 2)}
            for key, value in sorted(trend_data.items())   # ensures that the results are ordered chronologically by date.
        ]

        return Response(result, status=status.HTTP_200_OK)


class DashboardSummaryView(APIView):
    """
    Dashboard overview with:
    - total credit, debit, balance
    - recent transactions
    - top categories
    - 7-day trend data
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        now = datetime.now()

        # ✅ All-time totals
        total_credit = Transaction.objects.filter(user=user, transaction_type='credit').aggregate(Sum('amount'))['amount__sum'] or 0
        total_debit = Transaction.objects.filter(user=user, transaction_type='debit').aggregate(Sum('amount'))['amount__sum'] or 0
        balance = total_credit - total_debit

        # ✅ Recent Transactions (latest 5)
        recent_txns = Transaction.objects.filter(user=user).order_by('-date_time')[:5]
        recent_txns_data = []
        for txn in recent_txns:
            recent_txns_data.append({
                "id": txn.id,
                "amount": float(txn.amount),
                "transaction_type": txn.transaction_type,
                "category": txn.category.name if txn.category else None,
                "date": txn.date_time.date().isoformat(),
                "tags": [tag.name for tag in txn.tags.all()]
            })

        # ✅ Top Categories (by debit amount)
        top_categories = (
            Transaction.objects
            .filter(user=user, transaction_type='debit', category__isnull=False)
            .values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')[:3]
        )
        top_category_data = [{"category": cat['category__name'], "total": round(cat['total'], 2)} for cat in top_categories]

        # ✅ Trend data (last 7 days)
        trend_start = now - timedelta(days=6)
        trend_txns = (
            Transaction.objects
            .filter(user=user, date_time__date__gte=trend_start.date())
            .annotate(day=TruncDay('date_time'))    #allows grouping by day.
            .values('day', 'transaction_type')      #Groups the transactions by the day and the transaction_type.
            .annotate(total=Sum('amount'))
        )

        trend_data = {}
        for entry in trend_txns:
            day = entry['day'].date().isoformat()
            t_type = entry['transaction_type']
            trend_data.setdefault(day, {"credit": 0.0, "debit": 0.0})   #his ensures that each day has an initial credit and debit total of 0.0.
            trend_data[day][t_type] = float(entry['total'])     #Updates the credit or debit total for the current day based on the t_type

        # Fill missing days
        trend_result = []
        for i in range(7):    #Loops through the last 7 days.
            day = (trend_start + timedelta(days=i)).date().isoformat()
            trend_result.append({
                "date": day,
                "credit": round(trend_data.get(day, {}).get("credit", 0.0), 2),
                "debit": round(trend_data.get(day, {}).get("debit", 0.0), 2),
            })

        # ✅ Final response
        response = {
            "balance": round(balance, 2),
            "total_credit": round(total_credit, 2),
            "total_debit": round(total_debit, 2),
            "recent_transactions": recent_txns_data,
            "top_categories": top_category_data,
            "weekly_trend": trend_result
        }

        return Response(response, status=status.HTTP_200_OK)
    

class MonthlyReportAPIView(APIView):
    """
    Returns full financial report for the selected month.
    - Required: ?month=YYYY-MM
    - Always includes:
        - Total credit, debit, balance
        - Avg amount, savings rate
        - Top tags, top categories
        - Full transaction list
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        month_str = request.query_params.get("month")

        if not month_str:
            return Response({"error": "Month parameter is required (format: YYYY-MM)."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            month_dt = datetime.strptime(month_str, "%Y-%m")
        except ValueError:
            return Response({"error": "Invalid month format. Use YYYY-MM."},
                            status=status.HTTP_400_BAD_REQUEST)

        txns = Transaction.objects.filter(
            user=user,
            date_time__year=month_dt.year,
            date_time__month=month_dt.month
        )

        total_credit = txns.filter(transaction_type='credit').aggregate(Sum('amount'))['amount__sum'] or 0
        total_debit = txns.filter(transaction_type='debit').aggregate(Sum('amount'))['amount__sum'] or 0
        balance = total_credit - total_debit
        count = txns.count()
        avg_amount = round((total_credit + total_debit) / count, 2) if count else 0
        savings_rate = round(((total_credit - total_debit) / total_credit * 100), 2) if total_credit > 0 else 0

        # Top categories
        category_totals = (
            txns.filter(category__isnull=False)
            .values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')[:3]
        )
        top_categories = [cat['category__name'] for cat in category_totals]

        # Top tags
        tag_counter = defaultdict(int)
        for txn in txns:
            for tag in txn.tags.all():
                tag_counter[tag.name] += 1
        top_tags = sorted(tag_counter.items(), key=lambda x: x[1], reverse=True)[:3]     #Sorts this list of tuples in descending order based on the count
        top_tags = [tag for tag, _ in top_tags]

        # Full transaction list
        transaction_data = []
        for txn in txns.order_by('-date_time'):
            transaction_data.append({
                "id": txn.id,
                "amount": float(txn.amount),
                "transaction_type": txn.transaction_type,
                "category": txn.category.name if txn.category else None,
                "tags": [tag.name for tag in txn.tags.all()],
                "date": txn.date_time.date().isoformat(),
            })

        report = {
            "month": month_str,
            "total_credit": round(total_credit, 2),
            "total_debit": round(total_debit, 2),
            "balance": round(balance, 2),
            "transaction_count": count,
            "avg_transaction_amount": avg_amount,
            "savings_rate": savings_rate,
            "top_categories": top_categories,
            "top_tags": top_tags,
            "transactions": transaction_data
        }

        return Response(report, status=status.HTTP_200_OK)
    

class MonthlyReportPDFView(APIView):
    """
    Generates a PDF download for the selected month.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        month_str = request.query_params.get("month")

        if not month_str:
            return Response({"error": "Please provide 'month' (YYYY-MM)."}, status=status.HTTP_400_BAD_REQUEST)

        # Reuse logic from MonthlyReportAPIView
        try:
            month_dt = datetime.strptime(month_str, "%Y-%m")
        except ValueError:
            return Response({"error": "Invalid month format."}, status=status.HTTP_400_BAD_REQUEST)

        txns = Transaction.objects.filter(user=user, date_time__year=month_dt.year, date_time__month=month_dt.month)

        total_credit = txns.filter(transaction_type='credit').aggregate(Sum('amount'))['amount__sum'] or 0
        total_debit = txns.filter(transaction_type='debit').aggregate(Sum('amount'))['amount__sum'] or 0
        balance = total_credit - total_debit
        count = txns.count()
        avg_amount = round((total_credit + total_debit) / count, 2) if count else 0
        savings_rate = round(((total_credit - total_debit) / total_credit * 100), 2) if total_credit > 0 else 0

        # Top categories and tags
        category_totals = (
            txns.filter(category__isnull=False)
            .values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')[:3]
        )
        top_categories = [cat['category__name'] for cat in category_totals]

        tag_counter = defaultdict(int)
        for txn in txns:
            for tag in txn.tags.all():
                tag_counter[tag.name] += 1
        top_tags = sorted(tag_counter.items(), key=lambda x: x[1], reverse=True)[:3]
        top_tags = [tag for tag, _ in top_tags]

        transaction_data = []
        for txn in txns.order_by('-date_time'):
            transaction_data.append({
                "amount": float(txn.amount),
                "transaction_type": txn.transaction_type,
                "category": txn.category.name if txn.category else None,
                "tags": [tag.name for tag in txn.tags.all()],
                "date": txn.date_time.date().isoformat(),
            })

        report_data = {
            "month": month_str,
            "total_credit": round(total_credit, 2),
            "total_debit": round(total_debit, 2),
            "balance": round(balance, 2),
            "transaction_count": count,
            "avg_transaction_amount": avg_amount,
            "savings_rate": savings_rate,
            "top_categories": top_categories,
            "top_tags": top_tags,
            "transactions": transaction_data,
        }

        pdf_buffer = generate_monthly_report_pdf(report_data)

        return FileResponse(pdf_buffer, as_attachment=True, filename=f"report_{month_str}.pdf")
    

class MonthlyReportEmailView(APIView):
    """
    Sends the monthly report PDF to the user's email.
    URL: POST /api/app/transactions/monthly-report/email/?month=2025-04
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        month_str = request.query_params.get("month")

        if not month_str:
            return Response({"error": "Please provide 'month' (YYYY-MM)."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            month_dt = datetime.strptime(month_str, "%Y-%m")
        except ValueError:
            return Response({"error": "Invalid month format. Use YYYY-MM."}, status=status.HTTP_400_BAD_REQUEST)

        # Filter transactions for that user and month
        txns = Transaction.objects.filter(
            user=user,
            date_time__year=month_dt.year,
            date_time__month=month_dt.month
        )

        total_credit = txns.filter(transaction_type='credit').aggregate(Sum('amount'))['amount__sum'] or 0
        total_debit = txns.filter(transaction_type='debit').aggregate(Sum('amount'))['amount__sum'] or 0
        balance = total_credit - total_debit
        count = txns.count()
        avg_amount = round((total_credit + total_debit) / count, 2) if count else 0
        savings_rate = round(((total_credit - total_debit) / total_credit * 100), 2) if total_credit > 0 else 0

        category_totals = (
            txns.filter(category__isnull=False)
            .values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')[:3]
        )
        top_categories = [c['category__name'] for c in category_totals]

        tag_counter = defaultdict(int)
        for txn in txns:
            for tag in txn.tags.all():
                tag_counter[tag.name] += 1
        top_tags = sorted(tag_counter.items(), key=lambda x: x[1], reverse=True)[:3]
        top_tags = [t for t, _ in top_tags]

        transaction_data = []
        for txn in txns.order_by('-date_time'):
            transaction_data.append({
                "amount": float(txn.amount),
                "transaction_type": txn.transaction_type,
                "category": txn.category.name if txn.category else None,
                "tags": [tag.name for tag in txn.tags.all()],
                "date": txn.date_time.date().isoformat(),
            })

        report_data = {
            "month": month_str,
            "total_credit": round(total_credit, 2),
            "total_debit": round(total_debit, 2),
            "balance": round(balance, 2),
            "transaction_count": count,
            "avg_transaction_amount": avg_amount,
            "savings_rate": savings_rate,
            "top_categories": top_categories,
            "top_tags": top_tags,
            "transactions": transaction_data,
        }

        pdf_buffer = generate_monthly_report_pdf(report_data)
        send_monthly_report_email(user, month_str, pdf_buffer)

        return Response({"message": f"Report sent to {user.email} successfully."}, status=status.HTTP_200_OK)
    

class SmartMessageParserView(APIView):
    """
    Accepts a raw SMS-style message, extracts structured info using GPT,
    and saves as a Transaction for the user.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = MessageInputSerializer(data=request.data)
        if serializer.is_valid():
            try:
                transaction = parse_and_save_transaction_from_sms(
                    message=serializer.validated_data['message'],
                    user=request.user
                )
                
                # Build string message summary
                message_str = (
                    f"{transaction.transaction_type.title()} of ₹{transaction.amount:.2f} "
                    f"{'from' if transaction.transaction_type == 'debit' else 'to'} your account "
                    f"on {transaction.date_time.strftime('%d %b %Y, %I:%M %p')}."
                )

                if transaction.category:
                    message_str += f" Category: {transaction.category.name}."

                if transaction.description:
                    message_str += f" Note: {transaction.description}."

                if transaction.is_recurring:
                    message_str += " This is a recurring transaction."

                return Response(
                    {
                        "message": message_str,
                        "transaction_id": transaction.id
                    },
                    status=status.HTTP_201_CREATED
                )
            
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class AICSVParserView(APIView):
    """
    Upload a CSV file with SMS-style messages.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CSVUploadSerializer(data=request.data)
        if serializer.is_valid():
            file = serializer.validated_data['file']
            # This decodes the resulting base64 encoded bytes into a UTF-8 string, making it easier to handle and potentially pass around.
            file_base64 = base64.b64encode(file.read()).decode('utf-8')
            save_to_db = serializer.validated_data.get('save_to_db', False)
 
            # Dispatch to Celery
            process_csv_file_task.delay(file_base64, request.user.id, save_to_db)
            return Response(
                {
                    "message": "File uploaded. Background processing started.", 
                },
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class AICSVResultView(APIView):
    """
    Extract transactions from csv file,
    and optionally save to database. Returns summary insights + individual parsing results.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_id = request.user.id
        # This line attempts to retrieve data from Django's cache system
        result = cache.get(f"csv_result_{user_id}")
        if result:
            return Response(result)
        return Response(
            {
                "message": "No recent CSV processing result found."
            },
            status=status.HTTP_404_NOT_FOUND
        )
    

class ChatbotAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        query = request.data.get("message")
        mode = request.query_params.get("mode", "agent")  # Default to agent mode
        user_id = str(request.user.id)

        if not query:
            return Response(
                {
                    "error": "Message is required."
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        print(f"🧠 Chatbot invoked | user_id: {user_id} | mode: {mode} | message: {query}", flush=True)

        try:
            response = run_chatbot(query=query, user_id=user_id, mode=mode)
            return Response(
                {
                    "response": response
                }, 
                status=status.HTTP_200_OK
            )
        except Exception as e:
            print(f"❌ Chatbot error: {str(e)}", flush=True)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    def delete(self, request):
        user_id = str(request.user.id)
        deleted_count, _ = ChatHistory.objects.filter(user_id=user_id).delete()

        print(f"🗑 Deleted {deleted_count} chat messages for user_id: {user_id}", flush=True)

        return Response(
            {"message": f"Deleted {deleted_count} messages."},
            status=status.HTTP_200_OK
        )
