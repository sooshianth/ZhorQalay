from django.db import models
from django.contrib.auth.models import User
from django_jalali.db import models as jmodels
from django.db.models import Sum
import jdatetime

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
    approved_by_user1 = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="approver1", null=True, blank=True, verbose_name="تایید توسط کاربر 1")
    approved_by_user2 = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="approver2", null=True, blank=True, verbose_name="تایید توسط کاربر 2")
    approved_by_user3 = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="approver3", null=True, blank=True, verbose_name="تایید توسط کاربر 3")
    approved_by_admin = models.BooleanField(default=False, verbose_name='تایید توسط ادمین')
    user1_approved = models.BooleanField(default=False, verbose_name="تایید توسط کاربر 1 انجام شده")
    user2_approved = models.BooleanField(default=False, verbose_name="تایید توسط کاربر 2 انجام شده")
    user3_approved = models.BooleanField(default=False, verbose_name="تایید توسط کاربر 3 انجام شده")

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
    def is_enough_user_approvals(self):
        # حداقل دو کاربر از سه کاربر تایید کرده باشند
        approved_count = sum([
            1 if self.user1_approved else 0,
            1 if self.user2_approved else 0,
            1 if self.user3_approved else 0
        ])
        return approved_count >= 2

    @property
    def is_fully_approved(self):
        # حداقل دو کاربر تایید کرده باشند و ادمین هم تایید کرده باشد
        return self.is_enough_user_approvals and self.approved_by_admin
    
    def save(self, *args, **kwargs):
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
        super().save(*args, **kwargs)
        MonthlyAttendance.update_monthly_hours(self.employee, self.week_start_date)

    class Meta:
        verbose_name = "حضور هفتگی"
        verbose_name_plural = "حضور هفتگی"
        ordering = ['-week_start_date', 'employee']

    def __str__(self):
        return f"{self.employee.username} - {self.week_start_date}"

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
                
            total = WeeklyAttendance.objects.filter(
                employee=employee,
                week_start_date__gte=start_of_month,
                week_start_date__lte=end_of_month
            ).aggregate(Sum('total_hours'))['total_hours__sum'] or 0
            
            print(f"Debug - update_monthly_hours: Total hours: {total}")
            
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