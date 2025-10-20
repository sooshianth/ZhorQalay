from django.db import models
from django.contrib.auth.models import User
from django_jalali.db import models as jmodels
from django.db.models import Sum, Q
import jdatetime
from .EmployeeModel import Employee
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

class WeeklyAttendance(models.Model):
    employee = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="کارمند")
    week_start_date = jmodels.jDateField(verbose_name="تاریخ حضور")  # تاریخی که کاربر انتخاب کرده و ساعت را ثبت می‌کند
    day = models.CharField(max_length=10, verbose_name="روز", null=True, blank=True)  # روز خاص
    saturday_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات شنبه", default=0)
    sunday_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات یکشنبه", default=0)
    monday_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات دوشنبه", default=0)
    tuesday_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات سه‌شنبه", default=0)
    wednesday_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات چهارشنبه", default=0)
    thursday_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات پنج‌شنبه", default=0)
    friday_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات جمعه", default=0)
    total_hours = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="مجموع ساعات", default=0)
    description = models.TextField(verbose_name='توضیحات', null=True, blank=True)
    approved_by_user1 = models.ForeignKey(Employee, on_delete=models.SET_NULL, related_name="approver1", null=True, blank=True, verbose_name="تایید توسط کاربر 1")
    approved_by_user2 = models.ForeignKey(Employee, on_delete=models.SET_NULL, related_name="approver2", null=True, blank=True, verbose_name="تایید توسط کاربر 2")
    approved_by_user3 = models.ForeignKey(Employee, on_delete=models.SET_NULL, related_name="approver3", null=True, blank=True, verbose_name="تایید توسط کاربر 3")
    approved_by_admin = models.BooleanField(default=False, verbose_name='تایید توسط ادمین')
    user1_approved = models.BooleanField(default=False, verbose_name="تایید توسط کاربر 1 انجام شده")
    user2_approved = models.BooleanField(default=False, verbose_name="تایید توسط کاربر 2 انجام شده")
    user3_approved = models.BooleanField(default=False, verbose_name="تایید توسط کاربر 3 انجام شده")
    
    # فیلدهای جدید برای کامنت‌های تایید
    user1_approval_comment = models.TextField(verbose_name="نظر تایید کاربر 1", null=True, blank=True)
    user2_approval_comment = models.TextField(verbose_name="نظر تایید کاربر 2", null=True, blank=True)
    user3_approval_comment = models.TextField(verbose_name="نظر تایید کاربر 3", null=True, blank=True)
    admin_approval_comment = models.TextField(verbose_name="نظر تایید ادمین", null=True, blank=True)
    
    # فیلدهای تاریخ تایید
    user1_approved_at = jmodels.jDateTimeField(verbose_name="تاریخ تایید کاربر 1", null=True, blank=True)
    user2_approved_at = jmodels.jDateTimeField(verbose_name="تاریخ تایید کاربر 2", null=True, blank=True)
    user3_approved_at = jmodels.jDateTimeField(verbose_name="تاریخ تایید کاربر 3", null=True, blank=True)
    admin_approved_at = jmodels.jDateTimeField(verbose_name="تاریخ تایید ادمین", null=True, blank=True)
    
    # فیلدهای جدید برای ردیابی تغییرات
    created_at = jmodels.jDateTimeField(default=timezone.now, verbose_name="تاریخ ایجاد")
    updated_at = jmodels.jDateTimeField(auto_now=True, verbose_name="تاریخ آخرین ویرایش")
    edit_count = models.PositiveIntegerField(default=0, verbose_name="تعداد ویرایش")
    is_locked = models.BooleanField(default=False, verbose_name="قفل شده (غیر قابل ویرایش)")
    
    # فیلد وضعیت
    STATUS_CHOICES = [
        ('DRAFT', 'پیش‌نویس'),
        ('PENDING_APPROVAL', 'در انتظار تایید'),
        ('PARTIALLY_APPROVED', 'تایید جزئی'),
        ('FULLY_APPROVED', 'تایید نهایی'),
        ('REJECTED', 'رد شده'),
        ('NEEDS_REVISION', 'نیاز به بازنگری'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name="وضعیت")
    
    # فیلدهای جدید برای رد کردن
    is_rejected = models.BooleanField(default=False, verbose_name="رد شده")
    rejected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='rejected_attendances', verbose_name="رد شده توسط")
    rejected_at = jmodels.jDateTimeField(null=True, blank=True, verbose_name="تاریخ رد")
    rejection_reason = models.TextField(null=True, blank=True, verbose_name="دلیل رد")
    rejection_comments = models.TextField(null=True, blank=True, verbose_name="نظرات رد")
    
    # فیلد برای نشان‌دادن اینکه آیا پس از رد، ویرایش شده یا نه
    revised_after_rejection = models.BooleanField(default=False, verbose_name="پس از رد ویرایش شده")
    
    # فیلد برای تشخیص ناهنجاری در ساعات کاری
    anomaly_detected = models.BooleanField(default=False, verbose_name="ناهنجاری تشخیص داده شده")

    def calculate_total_hours(self):
        # جمع ساعات روزانه، با اطمینان از اینکه مقادیر None به 0 تبدیل شوند
        hours = [
            self.saturday_hours or 0,
            self.sunday_hours or 0,
            self.monday_hours or 0,
            self.tuesday_hours or 0,
            self.wednesday_hours or 0,
            self.thursday_hours or 0,
            self.friday_hours or 0,
        ]
        self.total_hours = sum(float(hour) for hour in hours)

    @property
    def can_be_edited(self):
        """آیا این رکورد قابل ویرایش است؟"""
        if self.is_locked:
            return False
        # اگر رد شده، قابل ویرایش است
        if self.is_rejected:
            return True
        # اگر هیچ تاییدی نداشته باشد، قابل ویرایش است
        if not any([self.user1_approved, self.user2_approved, self.user3_approved, self.approved_by_admin]):
            return True
        return False

    @property
    def is_enough_user_approvals(self):
        # اگر رد شده، به حد نصاب نرسیده
        if self.is_rejected:
            return False
        # حداقل دو کاربر از سه کاربر تایید کرده باشند
        approved_count = sum([
            1 if self.user1_approved else 0,
            1 if self.user2_approved else 0,
            1 if self.user3_approved else 0
        ])
        return approved_count >= 2

    @property
    def is_fully_approved(self):
        # اگر رد شده، تایید نهایی نشده
        if self.is_rejected:
            return False
        # اگر ادمین تایید کرده باشد، کامل تایید شده محسوب می‌شود
        return self.approved_by_admin
    
    @property
    def approval_progress_percentage(self):
        """درصد پیشرفت تایید"""
        total_possible = 4  # 3 کاربر + 1 ادمین
        current_approvals = sum([
            1 if self.user1_approved else 0,
            1 if self.user2_approved else 0,
            1 if self.user3_approved else 0,
            1 if self.approved_by_admin else 0
        ])
        return (current_approvals / total_possible) * 100
    
    def get_approval_comments(self):
        """دریافت تمام نظرات تایید به صورت لیست ساده"""
        comments = []
        
        if self.user1_approved and self.user1_approval_comment:
            approver_name = str(self.approved_by_user1) if self.approved_by_user1 else 'کاربر 1'
            comments.append({
                'approver': approver_name,
                'comment': self.user1_approval_comment,
                'date': self.user1_approved_at.strftime('%Y/%m/%d %H:%M') if self.user1_approved_at else ''
            })
            
        if self.user2_approved and self.user2_approval_comment:
            approver_name = str(self.approved_by_user2) if self.approved_by_user2 else 'کاربر 2'
            comments.append({
                'approver': approver_name,
                'comment': self.user2_approval_comment,
                'date': self.user2_approved_at.strftime('%Y/%m/%d %H:%M') if self.user2_approved_at else ''
            })
            
        if self.user3_approved and self.user3_approval_comment:
            approver_name = str(self.approved_by_user3) if self.approved_by_user3 else 'کاربر 3'
            comments.append({
                'approver': approver_name,
                'comment': self.user3_approval_comment,
                'date': self.user3_approved_at.strftime('%Y/%m/%d %H:%M') if self.user3_approved_at else ''
            })
            
        if self.approved_by_admin and self.admin_approval_comment:
            comments.append({
                'approver': 'ادمین',
                'comment': self.admin_approval_comment,
                'date': self.admin_approved_at.strftime('%Y/%m/%d %H:%M') if self.admin_approved_at else ''
            })
            
        return comments
    
    def update_status(self):
        """به‌روزرسانی وضعیت بر اساس تاییدها و رد"""
        if self.is_rejected:
            if self.revised_after_rejection:
                self.status = 'NEEDS_REVISION'
            else:
                self.status = 'REJECTED'
        elif self.approved_by_admin:
            self.status = 'FULLY_APPROVED'
        elif self.is_enough_user_approvals:
            self.status = 'PARTIALLY_APPROVED'
        elif any([self.user1_approved, self.user2_approved, self.user3_approved]):
            self.status = 'PENDING_APPROVAL'
        else:
            self.status = 'DRAFT'
    
    def reject_attendance(self, user, reason, comments=None):
        """رد کردن ساعت کاری"""
        self.is_rejected = True
        self.rejected_by = user
        self.rejected_at = timezone.now()
        self.rejection_reason = reason
        self.rejection_comments = comments
        self.revised_after_rejection = False
        
        # ریست کردن تاییدها
        self.user1_approved = False
        self.user2_approved = False
        self.user3_approved = False
        self.approved_by_admin = False
        
        # پاک کردن کامنت‌های تایید
        self.user1_approval_comment = None
        self.user2_approval_comment = None
        self.user3_approval_comment = None
        self.admin_approval_comment = None
        
        self.update_status()
        self.save()
    
    def clear_rejection(self):
        """پاک کردن وضعیت رد (هنگام ویرایش پس از رد)"""
        self.is_rejected = False
        self.rejected_by = None
        self.rejected_at = None
        self.rejection_reason = None
        self.rejection_comments = None
        self.revised_after_rejection = True
        self.update_status()
        self.save()

    def save(self, *args, **kwargs):
        is_update = bool(self.pk)
        if is_update:
            self.edit_count += 1
        
        if self.day and not self.day.endswith('شنبه'):
            day_mapping = {
                'شنبه': 'شنبه',
                'یکشنبه': 'یکشنبه',
                'دوشنبه': 'دوشنبه',
                'سه‌شنبه': 'سه‌شنبه',
                'چهارشنبه': 'چهارشنبه',
                'پنج‌شنبه': 'پنج‌شنبه',
                'جمعه': 'جمعه'
            }
            self.day = day_mapping.get(self.day, self.day)
        
        # اطمینان از محاسبه total_hours قبل از ذخیره
        self.calculate_total_hours()
        
        # به‌روزرسانی وضعیت
        self.update_status()
        
        super().save(*args, **kwargs)
        MonthlyAttendance.update_monthly_hours(self.employee, self.week_start_date)

    class Meta:
        verbose_name = "حضور هفتگی"
        verbose_name_plural = "حضور هفتگی"
        ordering = ['-week_start_date', 'employee']

    def __str__(self):
        return f"{self.employee.username} - {self.week_start_date} - {self.get_status_display()}"

# مدل جدید برای ذخیره بازه‌های زمانی
class TimeRange(models.Model):
    attendance = models.ForeignKey(WeeklyAttendance, on_delete=models.CASCADE, related_name='time_ranges', verbose_name='ساعت کاری')
    start_time = models.TimeField(verbose_name='زمان شروع')
    end_time = models.TimeField(verbose_name='زمان پایان')
    duration = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='مدت زمان (ساعت)', default=0)
    
    class Meta:
        verbose_name = "بازه زمانی"
        verbose_name_plural = "بازه‌های زمانی"
        
    def save(self, *args, **kwargs):
        # محاسبه مدت زمان
        start_seconds = self.start_time.hour * 3600 + self.start_time.minute * 60 + self.start_time.second
        end_seconds = self.end_time.hour * 3600 + self.end_time.minute * 60 + self.end_time.second
        if end_seconds > start_seconds:
            duration_seconds = end_seconds - start_seconds
            self.duration = round(duration_seconds / 3600, 2)  # تبدیل به ساعت با دو رقم اعشار
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.start_time.strftime('%H:%M')} تا {self.end_time.strftime('%H:%M')}"

class MonthlyAttendance(models.Model):
    employee = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="کارمند")
    month = models.CharField(max_length=7, verbose_name="ماه (YYYY-MM)")
    total_hours = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="مجموع ساعات ماهانه", default=0)

    @classmethod
    def update_monthly_hours(cls, employee, week_start_date):
        # week_start_date حالا یک تاریخ جلالی است (jdatetime.date)
        # استخراج سال و ماه به فرمت YYYY-MM
        try:
            print(f"Debug - update_monthly_hours: Processing date: {week_start_date}, Type: {type(week_start_date)}")
            year = week_start_date.year
            month = week_start_date.month
            month_str = f"{year}-{month:02d}"
            print(f"Debug - update_monthly_hours: Extracted month: {month_str}")
            
            # جمع ساعات در این ماه
            # فیلتر کردن با تاریخ جلالی نیاز به روش متفاوتی دارد
            # محاسبه اول و آخر ماه در تقویم جلالی
            start_of_month = jdatetime.date(year, month, 1)
            if month == 12:
                end_of_month = jdatetime.date(year + 1, 1, 1) - jdatetime.timedelta(days=1)
            else:
                end_of_month = jdatetime.date(year, month + 1, 1) - jdatetime.timedelta(days=1)
                
            print(f"Debug - update_monthly_hours: Month range: {start_of_month} to {end_of_month}")
                
            # فقط ساعات تأیید شده توسط ادمین را حساب می‌کنیم
            # با توجه به تغییر منطق تایید، دیگر نیازی به تایید کاربران نیست
            total = WeeklyAttendance.objects.filter(
                employee=employee,
                week_start_date__gte=start_of_month,
                week_start_date__lte=end_of_month,
                approved_by_admin=True,  # فقط ساعات تأیید شده توسط ادمین
            ).aggregate(Sum('total_hours'))['total_hours__sum'] or 0
            
            print(f"Debug - update_monthly_hours: Total approved hours for {month_str}: {total}")
            
            obj, created = cls.objects.get_or_create(employee=employee, month=month_str)
            obj.total_hours = total
            obj.save()
        except Exception as e:
            print(f"Error in update_monthly_hours: {str(e)}")
            # در صورت خطا، از ماه رشته‌ای که در jdatetime وجود دارد استفاده می‌کنیم
            month_str = week_start_date.strftime('%Y-%m')
            total = 0  # در صورت خطا، ساعت را 0 در نظر می‌گیریم
            obj, created = cls.objects.get_or_create(employee=employee, month=month_str)
            obj.total_hours = total
            obj.save()

    class Meta:
        verbose_name = "حضور ماهانه"
        verbose_name_plural = "حضور ماهانه"
        unique_together = ('employee', 'month')

    def __str__(self):
        return f"{self.employee.username} - {self.month}"

class WorkCalendar(models.Model):
    date = jmodels.jDateField(verbose_name="تاریخ")
    is_holiday = models.BooleanField(default=False, verbose_name="تعطیل")
    working_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات کاری", default=8)

    class Meta:
        verbose_name = "تقویم کاری"
        verbose_name_plural = "تقویم کاری"
        ordering = ['date']

    def __str__(self):
        return f"{self.date} - {'تعطیل' if self.is_holiday else f'{self.working_hours} ساعت کاری'}"

class Salary(models.Model):
    employee = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="کارمند")
    month = models.CharField(max_length=7, verbose_name="ماه (YYYY-MM)")
    base_salary = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="حقوق پایه")
    overtime_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات اضافه‌کاری", default=0)
    overtime_pay = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="پرداخت اضافه‌کاری", default=0)
    deductions = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="کسری حقوق", default=0)
    total_salary = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="حقوق کل", editable=False)

    class Meta:
        verbose_name = "حقوق و مزایا"
        verbose_name_plural = "حقوق و مزایا"
        unique_together = ('employee', 'month')

    def calculate_total_salary(self):
        self.total_salary = self.base_salary + self.overtime_pay - self.deductions

    def save(self, *args, **kwargs):
        self.calculate_total_salary()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee.username} - {self.month}"

# مدل جدید برای مستندات ساعات کاری
class AttendanceDocument(models.Model):
    attendance = models.ForeignKey(WeeklyAttendance, on_delete=models.CASCADE, related_name='documents', verbose_name='ساعت کاری')
    file = models.FileField(upload_to='attendance_documents/%Y/%m/', verbose_name='فایل')
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ آپلود')
    
    class Meta:
        verbose_name = "مستند ساعت کاری"
        verbose_name_plural = "مستندات ساعت کاری"
        
    def __str__(self):
        return f"مستند برای {self.attendance.employee.username} - {self.attendance.week_start_date}"

# مدل جدید برای ردیابی تاریخچه تغییرات
class AttendanceHistory(models.Model):
    attendance = models.ForeignKey(WeeklyAttendance, on_delete=models.CASCADE, related_name='history', verbose_name='ساعت کاری')
    changed_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='تغییر توسط')
    changed_at = jmodels.jDateTimeField(auto_now_add=True, verbose_name='تاریخ تغییر')
    change_type = models.CharField(max_length=20, choices=[
        ('CREATE', 'ایجاد'),
        ('UPDATE', 'ویرایش'),
        ('APPROVE', 'تایید'),
        ('REJECT', 'رد'),
        ('COMMENT', 'اضافه کردن نظر')
    ], verbose_name='نوع تغییر')
    description = models.TextField(verbose_name='شرح تغییر')
    old_data = models.JSONField(null=True, blank=True, verbose_name='داده‌های قبلی')
    new_data = models.JSONField(null=True, blank=True, verbose_name='داده‌های جدید')
    
    class Meta:
        verbose_name = "تاریخچه تغییرات ساعت کاری"
        verbose_name_plural = "تاریخچه تغییرات ساعات کاری"
        ordering = ['-changed_at']
    
    def __str__(self):
        return f"{self.attendance} - {self.get_change_type_display()} توسط {self.changed_by.username}"


class AttendanceConfiguration(models.Model):
    """
    تنظیمات مربوط به تاخیر مجاز در ثبت ساعات کاری
    """
    allowed_delay_days = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(0), MaxValueValidator(30)],
        verbose_name="تعداد روز تاخیر مجاز",
        help_text="تعداد روزهایی که کارمند می‌تواند با تاخیر ساعات کاری ثبت کند"
    )
    
    consider_friday_exception = models.BooleanField(
        default=True,
        verbose_name="استثنا برای جمعه",
        help_text="در صورت فعال بودن، یک روز اضافی برای جمعه در نظر گرفته می‌شود"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
        help_text="آیا این تنظیمات فعال است"
    )
    
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="تاریخ ایجاد"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="تاریخ آخرین ویرایش"
    )
    
    class Meta:
        verbose_name = "تنظیمات تاخیر در ثبت"
        verbose_name_plural = "تنظیمات تاخیر در ثبت"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"تاخیر مجاز: {self.allowed_delay_days} روز"
    
    @classmethod
    def get_active_config(cls):
        """
        دریافت تنظیمات فعال
        """
        config = cls.objects.filter(is_active=True).first()
        if not config:
            # اگر تنظیماتی وجود نداشته باشد، تنظیمات پیش‌فرض ایجاد می‌کنیم
            config = cls.objects.create(
                allowed_delay_days=1,
                consider_friday_exception=True,
                is_active=True
            )
        return config
    
    def can_register_for_date(self, target_date):
        """
        بررسی اینکه آیا برای تاریخ مشخص شده می‌توان ساعت کاری ثبت کرد
        
        Args:
            target_date: تاریخ مورد نظر به فرمت jdatetime.date
            
        Returns:
            tuple: (can_register: bool, reason: str)
        """
        if not self.is_active:
            return True, "تنظیمات غیرفعال است"
        
        # تاریخ امروز به فرمت شمسی
        today = jdatetime.date.today()
        
        # محاسبه تعداد روز تفاوت
        days_diff = (today - target_date).days
        
        # اگر تاریخ آینده است، مجاز نیست
        if days_diff < 0:
            return False, "نمی‌توان برای تاریخ آینده ساعت کاری ثبت کرد"
        
        # اگر امروز است، مجاز است
        if days_diff == 0:
            return True, "ثبت برای امروز مجاز است"
        
        # بررسی روز هفته امروز
        today_weekday = today.weekday()  # 0=شنبه، 1=یکشنبه، ..., 6=جمعه
        
        # تعداد روز مجاز
        allowed_days = self.allowed_delay_days
        
        # اگر استثنا برای جمعه فعال است و امروز شنبه است
        if self.consider_friday_exception and today_weekday == 0:  # شنبه
            allowed_days += 1
        
        # بررسی نهایی
        if days_diff <= allowed_days:
            return True, f"ثبت برای {days_diff} روز پیش مجاز است"
        else:
            return False, f"حداکثر {allowed_days} روز تاخیر مجاز است، شما {days_diff} روز تاخیر دارید"
    
    def save(self, *args, **kwargs):
        """
        هنگام ذخیره، دیگر تنظیمات را غیرفعال می‌کنیم
        """
        if self.is_active:
            # غیرفعال کردن سایر تنظیمات
            AttendanceConfiguration.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class MonthlyTarget(models.Model):
    """
    هدف ساعت کاری ماهانه برای هر کارمند
    """
    employee = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="کارمند", related_name='monthly_targets')
    month = models.CharField(max_length=7, verbose_name="ماه (YYYY-MM)")
    target_hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        verbose_name="هدف ساعات ماهانه",
        help_text="تعداد ساعات هدف برای این ماه"
    )
    description = models.TextField(null=True, blank=True, verbose_name="توضیحات")
    created_at = jmodels.jDateTimeField(default=timezone.now, verbose_name="تاریخ ایجاد")
    updated_at = jmodels.jDateTimeField(auto_now=True, verbose_name="تاریخ آخرین ویرایش")
    
    class Meta:
        verbose_name = "هدف ماهانه"
        verbose_name_plural = "اهداف ماهانه"
        unique_together = ('employee', 'month')
        ordering = ['-month']
    
    def __str__(self):
        return f"{self.employee.username} - {self.month} - هدف: {self.target_hours} ساعت"
    
    @property
    def achieved_hours(self):
        """محاسبه ساعات انجام شده (فقط تأیید شده توسط ادمین)"""
        try:
            monthly_attendance = MonthlyAttendance.objects.get(employee=self.employee, month=self.month)
            return monthly_attendance.total_hours
        except MonthlyAttendance.DoesNotExist:
            return 0
    
    @property
    def achievement_percentage(self):
        """درصد دستیابی به هدف"""
        from decimal import Decimal
        if self.target_hours == 0:
            return 0
        return round((float(self.achieved_hours) / float(self.target_hours)) * 100, 2)
    
    @property
    def remaining_hours(self):
        """ساعات باقی‌مانده"""
        return max(0, self.target_hours - self.achieved_hours)
    
    @property
    def is_achieved(self):
        """آیا به هدف رسیده؟ (با در نظر گرفتن 10٪ تلرانس)"""
        from decimal import Decimal
        minimum_acceptable = self.target_hours * Decimal('0.9')  # 90٪ هدف
        return self.achieved_hours >= minimum_acceptable
    
    @property
    def status(self):
        """وضعیت دستیابی به هدف"""
        percentage = self.achievement_percentage
        if percentage >= 100:
            return "کامل"
        elif percentage >= 90:
            return "قابل قبول"
        elif percentage >= 75:
            return "نیاز به تلاش بیشتر"
        else:
            return "ضعیف"
    
    @property
    def status_color(self):
        """رنگ وضعیت برای نمایش"""
        percentage = self.achievement_percentage
        if percentage >= 100:
            return "success"
        elif percentage >= 90:
            return "info"
        elif percentage >= 75:
            return "warning"
        else:
            return "danger"


class WeeklySchedule(models.Model):
    """
    برنامه هفتگی حضور هر کارمند
    """
    DAY_CHOICES = [
        ('Saturday', 'شنبه'),
        ('Sunday', 'یکشنبه'),
        ('Monday', 'دوشنبه'),
        ('Tuesday', 'سه‌شنبه'),
        ('Wednesday', 'چهارشنبه'),
        ('Thursday', 'پنج‌شنبه'),
        ('Friday', 'جمعه'),
    ]
    
    employee = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="کارمند", related_name='weekly_schedules')
    day_of_week = models.CharField(max_length=10, choices=DAY_CHOICES, verbose_name="روز هفته")
    start_time = models.TimeField(verbose_name="زمان شروع", help_text="ساعت شروع حضور در دفتر")
    end_time = models.TimeField(verbose_name="زمان پایان", help_text="ساعت پایان حضور در دفتر")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    description = models.TextField(null=True, blank=True, verbose_name="توضیحات")
    created_at = jmodels.jDateTimeField(default=timezone.now, verbose_name="تاریخ ایجاد")
    updated_at = jmodels.jDateTimeField(auto_now=True, verbose_name="تاریخ آخرین ویرایش")
    
    class Meta:
        verbose_name = "برنامه هفتگی"
        verbose_name_plural = "برنامه‌های هفتگی"
        ordering = ['employee', 'day_of_week']
    
    def __str__(self):
        return f"{self.employee.username} - {self.get_day_of_week_display()} - {self.start_time.strftime('%H:%M')} تا {self.end_time.strftime('%H:%M')}"
    
    @property
    def duration_hours(self):
        """محاسبه مدت زمان به ساعت"""
        start_seconds = self.start_time.hour * 3600 + self.start_time.minute * 60
        end_seconds = self.end_time.hour * 3600 + self.end_time.minute * 60
        if end_seconds > start_seconds:
            duration_seconds = end_seconds - start_seconds
            return round(duration_seconds / 3600, 2)
        return 0
    
    def clean(self):
        """اعتبارسنجی داده‌ها"""
        from django.core.exceptions import ValidationError
        if self.end_time <= self.start_time:
            raise ValidationError("زمان پایان باید بعد از زمان شروع باشد")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)