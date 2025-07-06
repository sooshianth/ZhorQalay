from django.db import models
from django_jalali.db import models as jmodels
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q
from .NotificationModel import Notification
from django.core.cache import cache
from datetime import timedelta
import random
import string
import logging

logger = logging.getLogger("core_sales_agent")

class SalesAgent(models.Model):
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='sales_agent')
    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    dakheli_number = models.CharField(max_length=10, unique=True, null= True, blank=True)
    factor_code = models.CharField(max_length=2, unique=True, null=True, blank=True)
    target_monthly_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0, 
                                              verbose_name='هدف فروش ماهانه')
    
    class Meta:
        verbose_name = 'کارشناس فروش'
        verbose_name_plural = 'کارشناسان فروش'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['factor_code']),
        ]

    def get_all_customers(self):
        return self.customers.all()
    
    def get_sales_in_period(self, start_date=None, end_date=None, paid_only=True, archived=False):
        """
        دریافت خریدهای انجام شده در یک بازه زمانی با فیلترهای مختلف
        با توجه به سیستم استیجینگ جدید
        """
        from .PurchaseModel import Purchase
        
        if start_date is None:
            start_date = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if end_date is None:
            end_date = timezone.now()
            
        filters = Q(created_at__gte=start_date, created_at__lte=end_date)
        filters &= Q(unique_sales_agent=self)  # فیلتر مستقیم بر اساس unique_sales_agent
        
        # فیلتر بر اساس وضعیت پرداخت
        paid_states = [
            'PAYMENT_VERIFIED', 'ALLOCATION_APPROVED', 
            'VENDOR_SETTLED', 'ADDRESS_SENT', 'SENT_TO_SHIPPING', 
            'BARNAMEH_ISSUED', 'BARNAMEH_INCOMPLETE', 'DELIVERED', 'DIFFERENCE_APPROVED',
            'SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED',
            'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED',
            'FINANCIAL_APPROVED', 'COMPLETED'
        ]
        
        if paid_only:
            filters &= Q(state__in=paid_states)

        # وضعیت آرشیو
        if archived:
            filters &= Q(state='ARCHIVED')
        else:
            filters &= ~Q(state='ARCHIVED')
        
        return Purchase.objects.filter(filters)

    def get_this_month_sales(self):
        """دریافت همه خریدهای پرداخت شده و غیرآرشیوی ماه جاری."""
        now = timezone.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return self.get_sales_in_period(start_date=start_of_month, end_date=now)

    def get_this_month_sales_stats(self):
        """دریافت آمار جامع فروش ماه جاری با کش."""
        now = timezone.now()
        cache_key = f'sales_agent_{self.id}_monthly_stats_{now.strftime("%Y%m")}'
        cached_data = cache.get(cache_key)
        
        if cached_data is not None:
            return cached_data
                
        sales = self.get_this_month_sales()
        amount = sum(purchase.amount_paid for purchase in sales if purchase.amount_paid) or 0
        weight = sum(purchase.order_weight for purchase in sales) or 0
        count = len(sales)
        average = amount / count if count > 0 else 0
        target_achievement = (amount / self.target_monthly_sales * 100) if self.target_monthly_sales > 0 else 0
        
        result = {
            'amount': amount,
            'weight': weight / 1000,  # تبدیل به تن
            'count': count,
            'average': average,
            'target_achievement': target_achievement,
        }
        
        cache.set(cache_key, result, 3600)
        return result

    def get_potential_sales(self):
        """دریافت همه خریدهای پرداخت نشده و غیرآرشیوی (درآمد بالقوه آینده)."""
        from .PurchaseModel import Purchase
        
        now = timezone.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # وضعیت‌های پرداخت نشده
        unpaid_states = ['INITIATED', 'SMS_SENT']
        
        filters = Q(created_at__gte=start_of_month, created_at__lte=timezone.now())
        filters &= Q(state__in=unpaid_states)
        filters &= ~Q(state='ARCHIVED')
        filters &= Q(unique_sales_agent=self)  # فیلتر مستقیم بر اساس unique_sales_agent
        
        return Purchase.objects.filter(filters)
    
    def get_all_unpaid_sales(self):
        """دریافت همه خریدهای پرداخت نشده صرف نظر از وضعیت آرشیو."""
        from .PurchaseModel import Purchase
        
        # وضعیت‌های پرداخت نشده
        unpaid_states = ['INITIATED', 'SMS_SENT']
        
        filters = Q(state__in=unpaid_states)
        filters &= Q(unique_sales_agent=self)  # فیلتر مستقیم بر اساس unique_sales_agent
        
        return Purchase.objects.filter(filters)

    def get_all_active_sales(self):
        """دریافت همه خریدهای پرداخت شده و غیرآرشیوی."""
        from .PurchaseModel import Purchase
        
        # وضعیت‌های پرداخت شده و فعال
        active_states = [
            'PAYMENT_VERIFIED', 'ALLOCATION_APPROVED', 
            'VENDOR_SETTLED', 'ADDRESS_SENT', 'SENT_TO_SHIPPING', 
            'BARNAMEH_ISSUED', 'BARNAMEH_INCOMPLETE', 'DELIVERED', 'DIFFERENCE_APPROVED',
            'SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED',
            'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED',
            'FINANCIAL_APPROVED', 'COMPLETED'
        ]
        
        filters = Q(state__in=active_states)
        filters &= Q(unique_sales_agent=self)  # فیلتر مستقیم بر اساس unique_sales_agent
        
        return Purchase.objects.filter(filters)

    def get_all_archived_sales(self):
        """دریافت همه خریدهای آرشیو شده."""
        from .PurchaseModel import Purchase
        
        filters = Q(state='ARCHIVED')
        filters &= Q(unique_sales_agent=self)  # فیلتر مستقیم بر اساس unique_sales_agent
        
        return Purchase.objects.filter(filters)

    def get_tasks_by_status(self, status=None, due_date=None):
        tasks = []
        for customer in self.get_all_customers():
            query = Q()
            if status is not None:
                query &= Q(status=status)
            if due_date is not None:
                query &= Q(due_date__date=due_date)
                
            tasks.extend(customer.tasks.filter(query))
            
        return sorted(tasks, key=lambda task: task.due_date)

    def get_this_month_sales_weight(self):
        return sum([purchase.order_weight for purchase in self.get_this_month_sales()])

    def get_today_tasks(self):
        """دریافت همه تسک‌های سررسید امروز."""
        return self.get_tasks_by_status(due_date=timezone.now().date())

    def get_all_undone_tasks(self):
        """دریافت همه تسک‌های ناتمام مرتب شده بر اساس تاریخ سررسید."""
        return self.get_tasks_by_status(status=False)

    def get_all_tasks(self):
        """دریافت همه تسک‌ها مرتب شده بر اساس تاریخ سررسید."""
        return self.get_tasks_by_status()

    def get_overdue_tasks(self):
        """دریافت تمام تسک‌های ناتمامی که از تاریخ سررسیدشان گذشته است."""
        now = timezone.now()
        tasks = []
        for customer in self.get_all_customers():
            tasks.extend(customer.tasks.filter(status=False, due_date__lt=now))
        return sorted(tasks, key=lambda task: task.due_date)

    def get_weekly_sales_trend(self, weeks=8):
        """
        دریافت روند فروش هفتگی برای تعداد هفته‌های مشخص شده گذشته.
        
        Args:
            weeks: تعداد هفته‌های مورد نظر در روند
            
        Returns:
            دیکشنری از شماره هفته‌ها به وزن کل فروخته شده
        """
        from collections import defaultdict
        trend = defaultdict(int)
        
        # محاسبه تاریخ شروع (ابتدای هفته 'هفته' پیش)
        now = timezone.now()
        start_date = now - timedelta(days=now.weekday() + 7 * (weeks - 1))
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # دریافت همه خریدهای مرتبط
        purchases = self.get_sales_in_period(start_date=start_date, end_date=now, paid_only=True)
        
        # گروه‌بندی بر اساس هفته
        for purchase in purchases:
            week = purchase.created_at.isocalendar()[1]  # شماره هفته
            trend[week] += purchase.order_weight
            
        return dict(trend)

    def get_sales_by_product(self, start_date=None, end_date=None):
        """
        دریافت فروش‌ها بر اساس نوع محصول.
        
        Returns:
            دیکشنری از انواع محصول به وزن کل فروخته شده
        """
        from collections import defaultdict
        
        product_sales = defaultdict(int)
        sales = self.get_sales_in_period(start_date, end_date)
        
        for purchase in sales:
            if hasattr(purchase, 'product_type') and purchase.product_type:
                product_sales[purchase.product_type] += purchase.order_weight
            elif hasattr(purchase, 'cargo') and purchase.cargo and hasattr(purchase.cargo, 'product_type'):
                product_sales[purchase.cargo.get_product_type_display()] += purchase.order_weight
                
        return dict(product_sales)

    def check_task_deadlines(self):
        """
        بررسی سررسید تسک‌های آینده و ایجاد اعلان.
        تعداد اعلان‌های جدید ایجاد شده را برمی‌گرداند.
        """
        notification_count = 0
        now = timezone.now()
        
        for task in self.get_all_undone_tasks():
            # بررسی تسک‌های با سررسید کمتر از ۲۴ ساعت
            if task.due_date - now < timedelta(hours=24):
                # بررسی وجود اعلان قبلی
                notification_exists = Notification.objects.filter(
                    user=self.user,
                    message__contains=task.description,
                    created_at__gte=now - timedelta(hours=24)
                ).exists()
                
                if not notification_exists:
                    Notification.objects.create(
                        user=self.user,
                        message=f"تسک '{task.description}' تا کمتر از ۲۴ ساعت دیگر به پایان می‌رسد!",
                        is_read=False
                    )
                    notification_count += 1
                    
        return notification_count
    
    def forecast_sales(self, days_ahead=30):
        """
        پیش‌بینی فروش برای تعداد روزهای آینده مشخص شده.
        
        Args:
            days_ahead: تعداد روزهای پیش‌بینی
            
        Returns:
            دیکشنری با داده‌های پیش‌بینی
        """
        try:
            import numpy as np
            from sklearn.linear_model import LinearRegression
            
            # دریافت داده‌های تاریخی - ۹۰ روز گذشته
            now = timezone.now()
            start_date = now - timedelta(days=90)
            
            # آماده‌سازی داده بر اساس روز
            daily_sales = {}
            for i in range(90):
                day = start_date + timedelta(days=i)
                day_str = day.strftime('%Y-%m-%d')
                daily_sales[day_str] = 0
            
            # پر کردن داده‌های فروش واقعی
            sales = self.get_sales_in_period(start_date=start_date, end_date=now)
            for sale in sales:
                day_str = sale.created_at.strftime('%Y-%m-%d')
                daily_sales[day_str] = daily_sales.get(day_str, 0) + sale.weight
            
            # تبدیل به آرایه‌ها برای رگرسیون
            X = np.array(range(len(daily_sales))).reshape(-1, 1)
            y = np.array(list(daily_sales.values()))
            
            # آموزش مدل
            model = LinearRegression()
            model.fit(X, y)
            
            # پیش‌بینی آینده
            future_days = np.array(range(len(daily_sales), len(daily_sales) + days_ahead)).reshape(-1, 1)
            predictions = model.predict(future_days)
            
            # قالب‌بندی نتایج
            forecast_data = {}
            for i in range(days_ahead):
                future_date = now + timedelta(days=i+1)
                forecast_data[future_date.strftime('%Y-%m-%d')] = max(0, predictions[i])  # اطمینان از عدم منفی بودن
                
            return {
                'daily_forecast': forecast_data,
                'total_forecast': sum(forecast_data.values()),
                'confidence': model.score(X, y) * 100  
            }
            
        except ImportError:
            logger.warning("scikit-learn not installed, using simple moving average for forecast")
            return self._simple_forecast(days_ahead)
        except Exception as e:
            logger.error(f"Error in sales forecast: {str(e)}")
            return self._simple_forecast(days_ahead)
            
    def _simple_forecast(self, days_ahead=30):
        """پیش‌بینی میانگین متحرک ساده به عنوان پشتیبان."""
        now = timezone.now()
        start_date = now - timedelta(days=30)
        
        sales = self.get_sales_in_period(start_date=start_date, end_date=now)
        daily_avg = sum(s.weight for s in sales) / 30 if sales else 0
        
        forecast_data = {}
        for i in range(days_ahead):
            future_date = now + timedelta(days=i+1)
            forecast_data[future_date.strftime('%Y-%m-%d')] = daily_avg
            
        return {
            'daily_forecast': forecast_data,
            'total_forecast': daily_avg * days_ahead,
            'confidence': 50  # اطمینان ثابت برای روش ساده
        }

    def __str__(self):
        return self.name
    
    def clean(self):
        """اعتبارسنجی فیلدهای مدل."""
        if self.phone_number:
            if len(self.phone_number) < 11:
                raise ValidationError('شماره تلفن باید 11 رقم باشد.')
            if not self.phone_number.isdigit():
                raise ValidationError('شماره تلفن باید عدد باشد.')
        if not self.name:
            raise ValidationError('نام نمی‌تواند خالی باشد.')
        if len(self.name) < 3:
            raise ValidationError('نام باید حداقل 3 حرف باشد.')
        if len(self.name) > 100:
            raise ValidationError('نام نمی‌تواند بیشتر از 100 حرف باشد.')
        
    def save(self, *args, **kwargs):
        self.full_clean()
        if not self.factor_code and self.phone_number:
            self.factor_code = self.phone_number[-2:]
        elif not self.factor_code:
            self.factor_code = ''.join(random.choices(string.ascii_uppercase, k=2))
        super().save(*args, **kwargs)


from django.utils.translation import gettext_lazy as _
from core.SalesAgentModel import SalesAgent

class PhoneAssignment(models.Model):
    """مدل تخصیص شماره تلفن به کارشناسان فروش برای تماس و ویزیت"""
    
    STATUS_CHOICES = [
        ('pending', 'در انتظار تماس'),
        ('archived', 'بایگانی شده'),
        ('converted', 'تبدیل به مشتری'),
    ]
    
    phone_number = models.CharField(_("شماره تلفن"), max_length=20)
    sales_agent = models.ForeignKey(SalesAgent, on_delete=models.CASCADE, 
                                   related_name='assigned_phones',
                                   verbose_name=_("کارشناس فروش"))
    status = models.CharField(_("وضعیت"), max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(_("یادداشت"), blank=True, null=True)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_("تاریخ بروزرسانی"), auto_now=True)
    
    class Meta:
        verbose_name = _("تخصیص شماره")
        verbose_name_plural = _("تخصیص شماره‌ها")
        indexes = [
            models.Index(fields=['sales_agent', 'status']),
            models.Index(fields=['phone_number']),
        ]
        
    def __str__(self):
        return f"{self.phone_number} ({self.get_status_display()})"
    
    def clean(self):
        """اعتبارسنجی فیلدها"""
        # تمیز کردن شماره تلفن
        if self.phone_number:
            # تبدیل ارقام فارسی به انگلیسی
            persian_digits = "۰۱۲۳۴۵۶۷۸۹"
            english_digits = "0123456789"
            translation_table = str.maketrans(persian_digits, english_digits)
            self.phone_number = self.phone_number.translate(translation_table)
            
            # پاکسازی شماره از کاراکترهای غیرعددی
            self.phone_number = ''.join(c for c in self.phone_number if c.isdigit())
            
            # اگر با صفر شروع می‌شود، آن را حذف می‌کنیم
            if self.phone_number.startswith('0'):
                self.phone_number = self.phone_number[1:]
                
            # بررسی معیارهای اصلی
            if not self.phone_number.startswith('9'):
                raise models.ValidationError(_('شماره تلفن باید با 9 شروع شود'))
                
            if len(self.phone_number) != 10:
                raise models.ValidationError(_('شماره تلفن باید 10 رقم باشد'))
    
    def archive(self):
        """علامت‌گذاری به عنوان بایگانی شده"""
        self.status = 'archived'
        self.save()
    
    def mark_as_converted(self):
        """علامت‌گذاری به عنوان تبدیل شده به مشتری"""
        self.status = 'converted'
        self.save() 