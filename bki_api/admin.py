from django.contrib import admin
from .models import BKILog

@admin.register(BKILog)
class BKILogAdmin(admin.ModelAdmin):
    list_display = ('request_type', 'purchase', 'is_successful', 'created_at')
    list_filter = ('request_type', 'is_successful', 'created_at')
    search_fields = ('request_data', 'response_data', 'error_message')
    readonly_fields = ('created_at',)
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
