from django.contrib import admin
from .models import ExcelFile, BGExcelFile, ExcelProcessingLog


@admin.register(ExcelFile)
class ExcelFileAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'file_type', 'created_at', 'is_processed', 'is_approved')
    list_filter = ('file_type', 'is_processed', 'is_approved', 'created_at')
    search_fields = ('title', 'description', 'user__username')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(BGExcelFile)
class BGExcelFileAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'cargo', 'created_at', 'is_processed', 'is_approved')
    list_filter = ('is_processed', 'is_approved', 'created_at')
    search_fields = ('title', 'description', 'user__username', 'cargo__cottage')
    readonly_fields = ('file_type', 'created_at', 'updated_at')


@admin.register(ExcelProcessingLog)
class ExcelProcessingLogAdmin(admin.ModelAdmin):
    list_display = ('excel_file', 'processed_by', 'processed_at', 'success', 'records_processed', 'records_updated', 'records_failed')
    list_filter = ('success', 'processed_at')
    search_fields = ('excel_file__title', 'processed_by__username', 'log_message')
    readonly_fields = ('processed_at',)
