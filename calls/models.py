from django.db import models
from django.contrib.auth.models import User
from core.CustomerModel import Customer
from django.utils import timezone
import json
import requests
from django.conf import settings


class CallQueue(models.Model):
    """
    مدل صف تماس برای ذخیره شماره‌های انتظار تماس
    """
    SOURCE_CHOICES = [
        ('customer', 'مشتری'),
        ('manual', 'دستی'),
        ('suggestion', 'پیشنهادی'),
        ('excel', 'اکسل'),
    ]
    
    STATUS_CHOICES = [
        ('waiting', 'در انتظار'),
        ('calling', 'در حال تماس'),
        ('not_answered', 'پاسخ داده نشد'),
        ('answered_no_ivr', 'پاسخ داد اما وارد IVR نشد'),
        ('answered_ivr', 'پاسخ داد و وارد IVR شد'),
        ('busy', 'مشغول'),
    ]
    
    session_id = models.CharField(max_length=100, verbose_name='شناسه جلسه', help_text='برای گروه‌بندی شماره‌ها در یک جلسه کاری')
    phone_number = models.CharField(max_length=20, verbose_name='شماره تلفن')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True, verbose_name='مشتری')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, verbose_name='منبع')
    added_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='اضافه شده توسط')
    
    # Call status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting', verbose_name='وضعیت تماس')
    call_duration = models.IntegerField(null=True, blank=True, verbose_name='مدت تماس (ثانیه)')
    assigned_agent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_queue_calls', verbose_name='نماینده فروش اختصاص یافته')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    call_started_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان شروع تماس')
    call_ended_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان پایان تماس')
    
    class Meta:
        verbose_name = 'صف تماس'
        verbose_name_plural = 'صف‌های تماس'
        unique_together = ['session_id', 'phone_number']
        
    def __str__(self):
        return f"{self.phone_number} - {self.get_source_display()}"


class AutomaticCall(models.Model):
    """
    مدل برای مدیریت تماس‌های اتوماتیک
    """
    CALL_STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('in_progress', 'در حال انجام'),
        ('paused', 'متوقف موقت'),
        ('completed', 'تکمیل شده'),
        ('failed', 'ناموفق'),
        ('cancelled', 'لغو شده'),
    ]

    CALL_TYPE_CHOICES = [
        ('marketing', 'بازاریابی'),
        ('ad', 'تبلیغات'),
        ('status', 'وضعیت'),
        ('survey', 'نظرسنجی'),
        ('reminder', 'یادآوری'),
        ('notification', 'اطلاع‌رسانی'),
    ]

    title = models.CharField(max_length=200, verbose_name='عنوان تماس')
    description = models.TextField(blank=True, verbose_name='توضیحات')
    call_type = models.CharField(max_length=20, choices=CALL_TYPE_CHOICES, verbose_name='نوع تماس')
    
    # مدیریت زمان
    scheduled_time = models.DateTimeField(verbose_name='زمان برنامه‌ریزی شده')
    start_time = models.DateTimeField(null=True, blank=True, verbose_name='زمان شروع')
    end_time = models.DateTimeField(null=True, blank=True, verbose_name='زمان پایان')
    
    # وضعیت و اولویت
    status = models.CharField(max_length=20, choices=CALL_STATUS_CHOICES, default='pending', verbose_name='وضعیت')
    priority = models.IntegerField(default=1, verbose_name='اولویت')
    
    # ارتباط با کاربران
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_calls', verbose_name='ایجاد شده توسط')
    
    # تنظیمات پیامک/تماس
    phone_numbers = models.TextField(help_text='شماره‌های تلفن جدا شده با کاما', verbose_name='شماره‌های تلفن')
    message_template = models.TextField(blank=True, verbose_name='قالب پیام')
    
    # Asterisk integration settings
    asterisk_api_url = models.CharField(max_length=200, default='http://192.168.100.128:5000/api/start-dialer', verbose_name='آدرس API استریسک')
    asterisk_api_key = models.CharField(max_length=100, blank=True, verbose_name='کلید API استریسک')
    
    # Queue reference
    queue_session_id = models.CharField(max_length=100, blank=True, verbose_name='شناسه جلسه صف')
    
    # آمار
    total_calls = models.IntegerField(default=0, verbose_name='تعداد کل تماس‌ها')
    successful_calls = models.IntegerField(default=0, verbose_name='تماس‌های موفق')
    failed_calls = models.IntegerField(default=0, verbose_name='تماس‌های ناموفق')
    
    # تعداد تماس در دقیقه
    calls_per_minute = models.IntegerField(default=10, verbose_name='تعداد تماس در دقیقه')
    
    # زمان‌های سیستمی
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ به‌روزرسانی')

    class Meta:
        verbose_name = 'تماس اتوماتیک'
        verbose_name_plural = 'تماس‌های اتوماتیک'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"
    
    def start_asterisk_call(self):
        """
        شروع تماس از طریق Asterisk API
        """
        if not self.queue_session_id:
            return {'success': False, 'error': 'هیچ صفی تعریف نشده است'}

        # دریافت شماره‌های صف
        queue_numbers = CallQueue.objects.filter(session_id=self.queue_session_id).values_list('phone_number', flat=True)

        if not queue_numbers:
            return {'success': False, 'error': 'هیچ شماره‌ای در صف وجود ندارد'}

        # آماده‌سازی درخواست
        headers = {
            'Content-Type': 'application/json'
        }

        if self.asterisk_api_key:
            headers['X-API-KEY'] = self.asterisk_api_key

        data = {
            'numbers': list(queue_numbers),
            'title': self.title,
            'description': self.description,
            'call_type': self.call_type,
            'scheduled_time': self.scheduled_time.isoformat(),
            'priority': self.priority,
            'message_template': self.message_template,
            'calls_per_minute': self.calls_per_minute
        }

        try:
            response = requests.post(
                self.asterisk_api_url,
                headers=headers,
                data=json.dumps(data),
                timeout=30
            )

            if response.status_code == 200:
                self.status = 'in_progress'
                self.start_time = timezone.now()
                self.total_calls = len(queue_numbers)
                self.save()

                # ثبت لاگ
                CallLog.objects.create(
                    call=self,
                    event_type='asterisk_start',
                    message=f'تماس شروع شد با {len(queue_numbers)} شماره',
                    details={'response': response.json() if response.content else {}}
                )

                return {'success': True, 'message': 'تماس با موفقیت شروع شد'}
            else:
                CallLog.objects.create(
                    call=self,
                    event_type='asterisk_error',
                    message=f'خطا در شروع تماس: {response.status_code}',
                    details={'response': response.text}
                )
                return {'success': False, 'error': f'خطا در API: {response.status_code} - {response.text[:100]}'}

        except requests.ConnectionError as e:
            error_msg = 'امکان اتصال به سرور Asterisk وجود ندارد. لطفا بررسی کنید که سرور روشن باشد.'
            CallLog.objects.create(
                call=self,
                event_type='asterisk_connection_error',
                message=error_msg,
                details={'error': str(e)}
            )
            return {'success': False, 'error': error_msg}
        except requests.Timeout as e:
            error_msg = 'زمان اتصال به سرور Asterisk به پایان رسید. لطفا دوباره تلاش کنید.'
            CallLog.objects.create(
                call=self,
                event_type='asterisk_timeout',
                message=error_msg,
                details={'error': str(e)}
            )
            return {'success': False, 'error': error_msg}
        except requests.RequestException as e:
            CallLog.objects.create(
                call=self,
                event_type='asterisk_error',
                message=f'خطا در ارتباط با Asterisk: {str(e)}',
                details={'error': str(e)}
            )
            return {'success': False, 'error': f'خطا در ارتباط با Asterisk: {str(e)}'}


class CallLog(models.Model):
    """
    مدل برای ثبت لاگ‌های تماس‌ها
    """
    call = models.ForeignKey(AutomaticCall, on_delete=models.CASCADE, related_name='logs', verbose_name='تماس')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='زمان')
    event_type = models.CharField(max_length=50, verbose_name='نوع رویداد')
    message = models.TextField(verbose_name='پیام')
    details = models.JSONField(null=True, blank=True, verbose_name='جزئیات')
    
    class Meta:
        verbose_name = 'لاگ تماس'
        verbose_name_plural = 'لاگ‌های تماس‌ها'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.call.title} - {self.event_type}"
