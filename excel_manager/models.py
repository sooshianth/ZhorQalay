from django.db import models
from django_jalali.db import models as jmodels
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
import os
from core._models import CargoProduct


class ExcelFile(models.Model):
    """
    مدل پایه برای فایل‌های اکسل
    """
    EXCEL_TYPE_CHOICES = [
        ('bge', 'بازارگاه'),
        ('customer', 'مشتریان'),
        ('purchase', 'خرید'),
        ('other', 'سایر'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_excel_files', verbose_name=_('کاربر'))
    title = models.CharField(max_length=100, verbose_name=_('عنوان'))
    file = models.FileField(upload_to='excel_files/', verbose_name=_('فایل'))
    file_type = models.CharField(max_length=20, choices=EXCEL_TYPE_CHOICES, default='other', verbose_name=_('نوع فایل'))
    description = models.TextField(blank=True, null=True, verbose_name=_('توضیحات'))
    created_at = jmodels.jDateTimeField(auto_now_add=True, verbose_name=_('تاریخ ایجاد'))
    updated_at = jmodels.jDateTimeField(auto_now=True, verbose_name=_('تاریخ بروزرسانی'))
    is_processed = models.BooleanField(default=False, verbose_name=_('پردازش شده'))
    is_approved = models.BooleanField(default=False, verbose_name=_('تأیید شده'))
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_excel_files', verbose_name=_('تأیید شده توسط'))
    approved_at = jmodels.jDateTimeField(null=True, blank=True, verbose_name=_('تاریخ تأیید'))
    cleaned_file = models.FileField(upload_to='cleaned_excel_files/', null=True, blank=True, verbose_name=_('فایل تمیز شده'))

    class Meta:
        verbose_name = _('فایل اکسل')
        verbose_name_plural = _('فایل‌های اکسل')

    def __str__(self):
        return self.title
    
    def change_file_name(self, new_name):
        """
        تغییر نام فایل
        """
        try:
            if not self.file or not self.file.path:
                return False
                
            old_path = self.file.path
            if not os.path.exists(old_path):
                return False
                
            directory = os.path.dirname(old_path)
            new_path = os.path.join(directory, new_name)
            
            # ذخیره نام فایل جدید در دیتابیس
            self.file.name = os.path.join('excel_files', new_name)
            self.save(update_fields=['file'])
            
            # تغییر نام فایل فیزیکی
            if os.path.exists(old_path):
                os.rename(old_path, new_path)
            
            return True
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"خطا در تغییر نام فایل: {str(e)}")
            return False

    def return_path(self):
        """
        بازگرداندن مسیر فایل
        """
        return self.file.path


class BGExcelFile(ExcelFile):
    """
    مدل مخصوص فایل‌های اکسل بازارگاه
    """
    cargo = models.ForeignKey(CargoProduct, on_delete=models.CASCADE, related_name='cargo_excel_files', verbose_name=_('محصول'))
    
    class Meta:
        verbose_name = _('فایل اکسل بازارگاه')
        verbose_name_plural = _('فایل‌های اکسل بازارگاه')

    def save(self, *args, **kwargs):
        self.file_type = 'bge'
        super().save(*args, **kwargs)


class ExcelProcessingLog(models.Model):
    """
    ثبت گزارش‌های پردازش فایل‌های اکسل
    """
    excel_file = models.ForeignKey(ExcelFile, on_delete=models.CASCADE, related_name='processing_logs', verbose_name=_('فایل اکسل'))
    processed_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='excel_processing_logs', verbose_name=_('پردازش توسط'))
    processed_at = jmodels.jDateTimeField(auto_now_add=True, verbose_name=_('تاریخ پردازش'))
    success = models.BooleanField(default=True, verbose_name=_('موفقیت‌آمیز'))
    records_processed = models.PositiveIntegerField(default=0, verbose_name=_('تعداد رکوردهای پردازش شده'))
    records_updated = models.PositiveIntegerField(default=0, verbose_name=_('تعداد رکوردهای بروزرسانی شده'))
    records_failed = models.PositiveIntegerField(default=0, verbose_name=_('تعداد رکوردهای ناموفق'))
    log_message = models.TextField(blank=True, null=True, verbose_name=_('پیام گزارش'))

    class Meta:
        verbose_name = _('گزارش پردازش اکسل')
        verbose_name_plural = _('گزارش‌های پردازش اکسل')

    def __str__(self):
        return f"{self.excel_file.title} - {self.processed_at}"
