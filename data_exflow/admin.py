from django.contrib import admin
from .models import ImportExportSession, ImportExportLog, ImportRecord

class ImportExportLogInline(admin.TabularInline):
    model = ImportExportLog
    extra = 0
    readonly_fields = ('log_level', 'message', 'row_number', 'created_at')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

class ImportRecordInline(admin.TabularInline):
    model = ImportRecord
    extra = 0
    readonly_fields = ('content_type', 'object_id', 'row_number', 'action', 'previous_state', 'current_state', 'created_at')
    can_delete = False
    max_num = 10
    
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(ImportExportSession)
class ImportExportSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'session_type', 'content_type', 'user', 'status', 'row_count', 'processed_count', 'error_count', 'created_at')
    list_filter = ('session_type', 'status', 'created_at', 'content_type')
    search_fields = ('id', 'file_name', 'user__username')
    readonly_fields = ('id', 'session_type', 'content_type', 'user', 'file', 'file_name', 'file_type', 'created_at', 'updated_at', 'row_count', 'processed_count', 'error_count', 'mapping')
    inlines = [ImportExportLogInline, ImportRecordInline]
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        # Only allow viewing, not editing
        return True
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deleting through admin
        return False

@admin.register(ImportExportLog)
class ImportExportLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'log_level', 'message', 'row_number', 'created_at')
    list_filter = ('log_level', 'created_at')
    search_fields = ('message',)
    readonly_fields = ('session', 'log_level', 'message', 'row_number', 'created_at')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        # Only allow viewing, not editing
        return True
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deleting through admin
        return False
