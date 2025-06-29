from django.db import models
from django.utils.timezone import now

from app.models import CustomUser

# Create your models here.
# Category model
# Represents categories that transactions can be classified into (e.g., Food, Entertainment, etc.)
class Category(models.Model):
    # Name of the category, limited to 100 characters
    name = models.CharField(max_length=100)
    
    # Foreign key relationship with the CustomUser model to specify which user created the category
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='categories')

    def __str__(self):
        return self.name  # Returns the category name when the category object is printed

# Tag model   
class Tag(models.Model):
    """
    Custom tags that users can attach to transactions.
    """
    name = models.CharField(max_length=50)
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='tags')

    def __str__(self):
        return self.name


# Transaction model
# Represents individual financial transactions made by users
class Transaction(models.Model):
    # Define the types of transactions: 'credit' (money added) or 'debit' (money spent)
    TRANSACTION_TYPES = [
        ('credit', 'Credit'),  # Credit transaction type (e.g., deposit, income)
        ('debit', 'Debit'),    # Debit transaction type (e.g., withdrawal, expense)
    ]

    # Foreign key relationship with the CustomUser model to link the transaction to a specific user
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='transactions')
    
    # Foreign key relationship with the Category model to classify the transaction (optional, can be null)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')

    # Optional description of the transaction
    description = models.TextField(blank=True, null=True, help_text="Optional description of the transaction")

    # The amount of money involved in the transaction (up to 10 digits with 2 decimal places)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # The type of transaction (either 'credit' or 'debit') selected from the predefined TRANSACTION_TYPES
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    
    # The timestamp for when the transaction occurred (default is the current time)
    date_time = models.DateTimeField(default=now)

    is_recurring = models.BooleanField(default=False, help_text="Set to True if this is a recurring transaction")

    tags = models.ManyToManyField(Tag, blank=True, related_name='transactions')

    def __str__(self):
        # Returns a string representation of the transaction with its type, amount, and timestamp
        return f"{self.transaction_type} - {self.amount} ({self.date_time})"
    
# ChatHistory model
class ChatHistory(models.Model):
    user_id = models.CharField(max_length=255)
    user_message = models.TextField()
    ai_response = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"User {self.user_id} - {self.timestamp}"
