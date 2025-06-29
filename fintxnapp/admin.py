from django.contrib import admin
from .models import Category, Transaction, Tag , ChatHistory

# Register your models here.
# Category Admin
# Customize how the Category model appears in the admin interface
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id','name', 'created_by')  # Columns to display in the list view
    search_fields = ('name', 'created_by__username')  # Search categories by name or created_by user
    list_filter = ('created_by',)  # Filter categories by the user who created them

# Transaction Admin
# Customize how the Transaction model appears in the admin interface
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id','user', 'category', 'amount', 'transaction_type', 'date_time')  # Columns to display
    search_fields = ('user__username', 'category__name')  # Search by user or category
    list_filter = ('transaction_type', 'category', 'user')  # Filters to display in the sidebar
    list_per_page = 25  # Number of records to display per page in the list view

# Tag Admin
class TagAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_by')
    search_fields = ('name', 'created_by__username')
    list_filter = ('created_by',)

# ChatHistory admin
class ChatHistoryAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'user_message', 'ai_response', 'timestamp')
    search_fields = ('user_id', 'user_message', 'ai_response')
    list_filter = ('user_id', 'timestamp')


admin.site.register(Category, CategoryAdmin)  
admin.site.register(Transaction, TransactionAdmin)  
admin.site.register(Tag, TagAdmin)
admin.site.register(ChatHistory, ChatHistoryAdmin)