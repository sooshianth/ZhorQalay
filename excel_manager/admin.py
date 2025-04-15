from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import ExcelFile, BGExcelFile, ExcelProcessingLog
import pandas as pd
import os
import re


@admin.register(ExcelFile)
class ExcelFileAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'file_type', 'created_at', 'is_processed', 'is_approved')
    list_filter = ('file_type', 'is_processed', 'is_approved', 'created_at')
    search_fields = ('title', 'description', 'user__username')
    readonly_fields = ('created_at', 'updated_at', 'excel_preview')

    def excel_preview(self, obj):
        if not obj.file:
            return format_html('<p>فایل اکسل موجود نیست</p>')
        
        file_path = obj.return_path()
        if not os.path.exists(file_path):
            return format_html('<p>فایل اکسل یافت نشد</p>')
        
        try:
            # بررسی فایل‌های xls که ممکن است محتوای HTML داشته باشند
            if file_path.lower().endswith('.xls'):
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(1000)  # خواندن بخشی از ابتدای فایل برای بررسی
                    
                    # اگر فایل حاوی تگ HTML باشد
                    if '<html' in content.lower() or '<table' in content.lower():
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            html_content = f.read()
                            
                            # استخراج بخش جدول از HTML
                            table_match = re.search(r'<table.*?</table>', html_content, re.DOTALL)
                            if table_match:
                                table_html = table_match.group(0)
                                return format_html(
                                    '<div style="font-family: Tahoma, Arial; direction: ltr;">{}</div>',
                                    mark_safe(table_html)
                                )
            
            # پردازش معمولی فایل‌های اکسل
            df = pd.read_excel(file_path, nrows=10)
            table_html = df.to_html(classes='table table-striped table-bordered', index=False)
            return format_html(
                '<div style="font-family: Tahoma, Arial; direction: ltr;">{}</div>',
                mark_safe(table_html)
            )
        except Exception as e:
            return format_html('<p>خطا در نمایش فایل اکسل: {}</p>', str(e))
    
    excel_preview.short_description = 'پیش‌نمایش فایل اکسل'


@admin.register(BGExcelFile)
class BGExcelFileAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'cargo', 'created_at', 'is_processed', 'is_approved')
    list_filter = ('is_processed', 'is_approved', 'created_at')
    search_fields = ('title', 'description', 'user__username', 'cargo__cottage')
    readonly_fields = ('file_type', 'created_at', 'updated_at', 'excel_preview')

    def excel_preview(self, obj):
        if not obj.file:
            return format_html('<p>فایل اکسل موجود نیست</p>')
        
        file_path = obj.return_path()
        if not os.path.exists(file_path):
            return format_html('<p>فایل اکسل یافت نشد</p>')
        
        try:
            # بررسی فایل‌های xls که ممکن است محتوای HTML داشته باشند
            if file_path.lower().endswith('.xls'):
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(1000)  # خواندن بخشی از ابتدای فایل برای بررسی
                    
                    # اگر فایل حاوی تگ HTML باشد
                    if '<html' in content.lower() or '<table' in content.lower():
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            html_content = f.read()
                            
                            # استخراج بخش جدول از HTML
                            table_match = re.search(r'<table.*?</table>', html_content, re.DOTALL)
                            if table_match:
                                table_html = table_match.group(0)
                                return format_html(
                                    '<div style="font-family: Tahoma, Arial; direction: ltr;">{}</div>',
                                    mark_safe(table_html)
                                )
            
            # پردازش معمولی فایل‌های اکسل
            df = pd.read_excel(file_path, nrows=10)
            table_html = df.to_html(classes='table table-striped table-bordered', index=False)
            return format_html(
                '<div style="font-family: Tahoma, Arial; direction: ltr;">{}</div>',
                mark_safe(table_html)
            )
        except Exception as e:
            return format_html('<p>خطا در نمایش فایل اکسل: {}</p>', str(e))
    
    excel_preview.short_description = 'پیش‌نمایش فایل اکسل'


@admin.register(ExcelProcessingLog)
class ExcelProcessingLogAdmin(admin.ModelAdmin):
    list_display = ('excel_file', 'processed_by', 'processed_at', 'success', 'records_processed', 'records_updated', 'records_failed')
    list_filter = ('success', 'processed_at')
    search_fields = ('excel_file__title', 'processed_by__username', 'log_message')
    readonly_fields = ('processed_at',)
