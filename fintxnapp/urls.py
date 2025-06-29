from django.urls import path
from .views import (
    TagListView,
    CategoryView, 
    TransactionView, 
    TransactionDetailView,
    UserBalanceView,
    TransactionCategoryPercentageView, 
    MonthlySummaryView,
    TopCategoriesView,
    TopTransactionsView,
    SpendingTrendView,
    DashboardSummaryView,
    MonthlyReportAPIView,
    MonthlyReportPDFView,
    MonthlyReportEmailView,
    SmartMessageParserView,
    AICSVParserView,
    AICSVResultView,
    ChatbotAPIView,
)

urlpatterns = [
    # URL pattern for managing tags
    path('tags/', TagListView.as_view(), name='tag-list'),
    # URL pattern for managing categories (listing and creating categories)
    path('categories/', CategoryView.as_view(), name='category'),
    # URL pattern for managing transactions (listing and creating transactions and also for filtering)
    path('transactions/', TransactionView.as_view(), name='transaction'),
    # URL pattern for managing transactions (listing single transaction and also update and destroy it)
    path('transactions/<int:pk>/', TransactionDetailView.as_view(), name='transaction-detail'),
    # URL pattern for retrieving the user's current balance
    path('balance/', UserBalanceView.as_view(), name='balance'),
    # URL pattern for retrieving the transaction category data with percentages
    path('transactions/category-percentage/', TransactionCategoryPercentageView.as_view(), name='category-percentage'),
    # URL pattern for retrieving the transaction monthly summary(transcation_count, avg_amount, saving_rate etc....)
    path('transactions/monthly-summary/', MonthlySummaryView.as_view(), name='monthly-summary'),
    # URL pattern for retrieving the transactions of top n categories
    path('transactions/top-categories/', TopCategoriesView.as_view(), name='top-categories'),
    # URL pattern for retrieving the top n transactions (credit / debit)
    path('transactions/top/', TopTransactionsView.as_view(), name='top-transactions'),
    # URL pattern for retrieving trends for credit and debit totals grouped by day or week
    path('transactions/trends/', SpendingTrendView.as_view(), name='spending-trend'),
    # URL pattern for showing all key financial data on the frontend dashboard.
    path('dashboard/summary/', DashboardSummaryView.as_view(), name='dashboard-summary'),
    # URL pattern for showing monthly report.
    path('transactions/monthly-report/', MonthlyReportAPIView.as_view(), name='monthly-report'),
    # URL pattern for downloading monthly report in pdf formate.
    path('transactions/monthly-report/pdf/', MonthlyReportPDFView.as_view(), name='monthly-report-pdf'),
    # URL pattern for sending monthly report via email to user.
    path('transactions/monthly-report/email/', MonthlyReportEmailView.as_view(), name='monthly-report-email'),
    # URL pattern for extracting structured info from sms and store it in the DB.
    path('ai/smart-parse/', SmartMessageParserView.as_view(), name='smart-message-parser'),
    # URL pattern for uploading the csv file.
    path('ai/csv-parser/', AICSVParserView.as_view(), name='ai-csv-parser'),
    # URL pattern for extracting structured info from SMS-csv file and give option to store it in the DB or not.
    path('ai/csv-result/', AICSVResultView.as_view(), name='ai-csv-result'),
    # URL pattern for the user interaction with the chatbot.
    path("ai/chat", ChatbotAPIView.as_view(), name="chatbot"),
]
