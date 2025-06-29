from django.contrib import admin
from .models import CustomUser

admin.site.site_header = 'Finance AI'                
admin.site.index_title = 'ALL APP TABLE'                
admin.site.site_title = 'adminsitration'

# Custom User Admin
# Customize how the CustomUser model appears in the admin interface
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('id','username', 'email', 'is_verified', 'date_joined')  # Columns to display in the list view
    search_fields = ('username', 'email')  # Fields to search by
    list_filter = ('is_verified', 'is_staff')  # Filters to display in the sidebar

# Register models with the admin site
admin.site.register(CustomUser, CustomUserAdmin)  # Register the CustomUser model with the admin customization