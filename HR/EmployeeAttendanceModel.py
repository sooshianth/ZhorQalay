from django.db import models
from django.contrib.auth.models import User
from django_jalali.db import models as jmodels
from django.db.models import Sum


class WeeklyAttendance(models.Model):
    employee = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="کارمند")
    week_start_date = models.DateField(verbose_name="تاریخ شروع هفته")  # تاریخ شروع هفته (شنبه)
    day = models.CharField(max_length=10, verbose_name="روز", null=True, blank=True)  # روز خاص
    saturday_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات شنبه", null=True, blank=True)
    sunday_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات یکشنبه", null=True, blank=True)
    monday_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات دوشنبه", null=True, blank=True)
    tuesday_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات سه‌شنبه", null=True, blank=True)
    wednesday_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات چهارشنبه", null=True, blank=True)
    thursday_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات پنج‌شنبه", null=True, blank=True)
    friday_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات جمعه", null=True, blank=True)
    total_hours = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="مجموع ساعات", editable=False)
    description = models.TextField(verbose_name='توضیحات', null=True, blank=True)
    approved_by_user1 = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="approver1", null=True, blank=True, verbose_name="تایید توسط کاربر 1")
    approved_by_user2 = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="approver2", null=True, blank=True, verbose_name="تایید توسط کاربر 2")
    approved_by_admin = models.BooleanField(default=False, verbose_name='تایید توسط ادمین')
    user1_approved = models.BooleanField(default=False, verbose_name="تایید توسط کاربر 1 انجام شده")
    user2_approved = models.BooleanField(default=False, verbose_name="تایید توسط کاربر 2 انجام شده")

    def calculate_total_hours(self):
        self.total_hours = sum([
            self.saturday_hours or 0,
            self.sunday_hours or 0,
            self.monday_hours or 0,
            self.tuesday_hours or 0,
            self.wednesday_hours or 0,
            self.thursday_hours or 0,
            self.friday_hours or 0,
        ])

    @property
    def is_fully_approved(self):
        return self.user1_approved and self.user2_approved and self.approved_by_admin
    
    def save(self, *args, **kwargs):
        self.calculate_total_hours()
        super().save(*args, **kwargs)
        from .EmployeeAttendanceModel import MonthlyAttendance
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
        month = week_start_date.strftime('%Y-%m')
        total = WeeklyAttendance.objects.filter(
            employee=employee,
            week_start_date__startswith=month[:7]
        ).aggregate(Sum('total_hours'))['total_hours__sum'] or 0
        obj, created = cls.objects.get_or_create(employee=employee, month=month)
        obj.total_hours = total
        obj.save()

    class Meta:
        verbose_name = "حضور ماهانه"
        verbose_name_plural = "حضور ماهانه"
        unique_together = ('employee', 'month')

    def __str__(self):
        return f"{self.employee.username} - {self.month}"
    

class WorkCalendar(models.Model):
    date = models.DateField(verbose_name="تاریخ")
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