from django.db import models
from django.contrib.auth.models import User
from django_jalali.db import models as jmodels
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from .EmployeeModel import Employee
import jdatetime


class MorqkTask(models.Model):
    """
    مدل وظیفه با امتیاز مرغک (Story Points)
    """
    MORQK_CHOICES = [
        (0.5, '0.5'),
        (1, '1'),
        (2, '2'),
        (3, '3'),
        (5, '5'),
        (8, '8'),
        (13, '13'),
        (20, '20'),
        (40, '40'),
    ]
    
    STATUS_CHOICES = [
        ('TODO', 'انجام نشده'),
        ('IN_PROGRESS', 'در حال انجام'),
        ('PENDING_APPROVAL', 'در انتظار تایید'),
        ('APPROVED', 'تایید شده'),
        ('REJECTED', 'رد شده'),
    ]
    
    title = models.CharField(max_length=200, verbose_name="عنوان وظیفه")
    description = models.TextField(verbose_name="شرح وظیفه", blank=True)
    
    # آیا به چند نفر واگذار شده؟
    is_multi_assigned = models.BooleanField(default=False, verbose_name="واگذاری چندنفره")
    
    # کارمند مسئول انجام وظیفه (برای تک نفره)
    assigned_to = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='morqk_tasks',
        verbose_name="واگذار شده به",
        null=True,
        blank=True
    )
    
    # مدیر ایجادکننده وظیفه
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_morqk_tasks',
        verbose_name="ایجاد شده توسط"
    )
    
    # مقدار مرغک
    morqk_value = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        choices=MORQK_CHOICES,
        verbose_name="مقدار مرغک",
        validators=[MinValueValidator(0.5)]
    )
    
    # وضعیت
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='TODO',
        verbose_name="وضعیت"
    )
    
    # تاریخ‌ها
    created_at = jmodels.jDateTimeField(default=timezone.now, verbose_name="تاریخ ایجاد")
    due_date = jmodels.jDateField(null=True, blank=True, verbose_name="مهلت انجام")
    completed_at = jmodels.jDateTimeField(null=True, blank=True, verbose_name="تاریخ تکمیل")
    approved_at = jmodels.jDateTimeField(null=True, blank=True, verbose_name="تاریخ تایید")
    
    # تایید کننده
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_morqk_tasks',
        verbose_name="تایید شده توسط"
    )
    
    # توضیحات اضافی
    completion_note = models.TextField(
        verbose_name="یادداشت تکمیل",
        blank=True,
        help_text="توضیحات کارمند هنگام تکمیل وظیفه"
    )
    
    approval_note = models.TextField(
        verbose_name="یادداشت تایید",
        blank=True,
        help_text="نظر مدیر هنگام تایید/رد"
    )
    
    rejection_note = models.TextField(
        verbose_name="دلیل رد",
        blank=True,
        help_text="دلیل رد توسط مدیر"
    )
    
    class Meta:
        verbose_name = "وظیفه مرغک"
        verbose_name_plural = "وظایف مرغک"
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.title} - {self.assigned_to.username} ({self.morqk_value} مرغک)"
    
    def mark_as_completed(self, note=""):
        """علامت‌گذاری به عنوان تکمیل شده"""
        self.status = 'PENDING_APPROVAL'
        self.completed_at = timezone.now()
        self.completion_note = note
        self.save()
    
    def approve(self, manager, note=""):
        """تایید وظیفه توسط مدیر"""
        self.status = 'APPROVED'
        self.approved_by = manager
        self.approved_at = timezone.now()
        self.approval_note = note
        self.save()
    
    def reject(self, manager, note=""):
        """رد وظیفه توسط مدیر"""
        self.status = 'REJECTED'
        self.approved_by = manager
        self.approved_at = timezone.now()
        self.rejection_note = note
        # پاک کردن تاریخ تکمیل
        self.completed_at = None
        self.save()


class MonthlyMorqkSummary(models.Model):
    """
    خلاصه مرغک‌های ماهانه هر کارمند
    """
    employee = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="کارمند")
    month = models.CharField(max_length=7, verbose_name="ماه (YYYY-MM)")
    
    # مجموع مرغک‌های تایید شده
    total_approved_morqk = models.DecimalField(
        max_digits=8,
        decimal_places=1,
        verbose_name="مجموع مرغک تایید شده",
        default=0
    )
    
    # تعداد وظایف
    total_tasks = models.PositiveIntegerField(verbose_name="تعداد کل وظایف", default=0)
    completed_tasks = models.PositiveIntegerField(verbose_name="تعداد وظایف تکمیل شده", default=0)
    approved_tasks = models.PositiveIntegerField(verbose_name="تعداد وظایف تایید شده", default=0)
    
    last_updated = jmodels.jDateTimeField(auto_now=True, verbose_name="آخرین به‌روزرسانی")
    
    class Meta:
        verbose_name = "خلاصه ماهانه مرغک"
        verbose_name_plural = "خلاصه‌های ماهانه مرغک"
        unique_together = ('employee', 'month')
        ordering = ['-month', 'employee']
    
    def __str__(self):
        return f"{self.employee.username} - {self.month} ({self.total_approved_morqk} مرغک)"
    
    @classmethod
    def update_monthly_morqk(cls, employee, task_date):
        """
        به‌روزرسانی خلاصه ماهانه مرغک
        
        Args:
            employee: کاربر
            task_date: تاریخ وظیفه (jdatetime.date یا jdatetime.datetime)
        """
        try:
            # استخراج سال و ماه
            if isinstance(task_date, jdatetime.datetime):
                year = task_date.year
                month = task_date.month
            else:
                year = task_date.year
                month = task_date.month
            
            month_str = f"{year}-{month:02d}"
            
            # محاسبه اول و آخر ماه
            start_of_month = jdatetime.datetime(year, month, 1)
            if month == 12:
                end_of_month = jdatetime.datetime(year + 1, 1, 1) - jdatetime.timedelta(seconds=1)
            else:
                end_of_month = jdatetime.datetime(year, month + 1, 1) - jdatetime.timedelta(seconds=1)
            
            # محاسبه آمار
            from django.db.models import Sum, Count
            
            all_tasks = MorqkTask.objects.filter(
                assigned_to=employee,
                created_at__gte=start_of_month,
                created_at__lte=end_of_month
            )
            
            approved_tasks = all_tasks.filter(status='APPROVED')
            
            total_morqk = approved_tasks.aggregate(
                total=Sum('morqk_value')
            )['total'] or 0
            
            completed_count = all_tasks.filter(
                status__in=['PENDING_APPROVAL', 'APPROVED']
            ).count()
            
            approved_count = approved_tasks.count()
            total_count = all_tasks.count()
            
            # ذخیره یا به‌روزرسانی
            obj, created = cls.objects.get_or_create(
                employee=employee,
                month=month_str
            )
            
            obj.total_approved_morqk = total_morqk
            obj.total_tasks = total_count
            obj.completed_tasks = completed_count
            obj.approved_tasks = approved_count
            obj.save()
            
        except Exception as e:
            print(f"خطا در به‌روزرسانی خلاصه ماهانه مرغک: {str(e)}")


class TaskAssignment(models.Model):
    """
    مدل تخصیص کارمند به وظیفه با درصد مشارکت
    برای وظایف چندنفره
    """
    task = models.ForeignKey(
        MorqkTask,
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name='وظیفه'
    )
    
    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='task_assignments',
        verbose_name='کارمند'
    )
    
    percentage = models.PositiveIntegerField(
        verbose_name='درصد مشارکت',
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text='درصد مشارکت این کارمند در انجام وظیفه'
    )
    
    # وضعیت این کارمند در وظیفه
    STATUS_CHOICES = [
        ('TODO', 'انجام نشده'),
        ('IN_PROGRESS', 'در حال انجام'),
        ('COMPLETED', 'تکمیل شده'),
        ('APPROVED', 'تایید شده'),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='TODO',
        verbose_name='وضعیت'
    )
    
    # تاریخ‌های مربوط به این کارمند
    started_at = jmodels.jDateTimeField(null=True, blank=True, verbose_name='تاریخ شروع')
    completed_at = jmodels.jDateTimeField(null=True, blank=True, verbose_name='تاریخ تکمیل')
    
    # یادداشت کارمند هنگام تکمیل
    completion_note = models.TextField(blank=True, verbose_name='یادداشت تکمیل')
    
    class Meta:
        verbose_name = 'تخصیص کارمند به وظیفه'
        verbose_name_plural = 'تخصیص‌های کارمندان به وظایف'
        unique_together = ('task', 'employee')
        ordering = ['-percentage']
    
    def __str__(self):
        return f"{self.employee.username} - {self.task.title} ({self.percentage}%)"
    
    def get_morqk_share(self):
        """محاسبه سهم مرغک این کارمند"""
        if self.task.morqk_value:
            return (self.task.morqk_value * self.percentage) / 100
        return 0
    
    def mark_as_completed(self, note=""):
        """علامت‌گذاری به عنوان تکمیل شده"""
        self.status = 'COMPLETED'
        self.completed_at = timezone.now()
        self.completion_note = note
        self.save()
    
    def mark_as_approved(self):
        """علامت‌گذاری به عنوان تایید شده"""
        self.status = 'APPROVED'
        self.save()

