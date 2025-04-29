from django.db import models
from django.contrib.auth.models import User
import jdatetime

class WeeklyAttendance(models.Model):
    employee = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="کارمند")
    week_start_date = models.DateField(verbose_name="تاریخ شروع هفته")  # تاریخ شروع هفته (شنبه)
    saturday_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات شنبه", null=True, blank=True)
    sunday_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات یکشنبه", null=True, blank=True)
    monday_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات دوشنبه", null=True, blank=True)
    tuesday_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات سه‌شنبه", null=True, blank=True)
    wednesday_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات چهارشنبه", null=True, blank=True)
    thursday_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات پنج‌شنبه", null=True, blank=True)
    friday_hours = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="ساعات جمعه", null=True, blank=True)
    total_hours = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="مجموع ساعات", editable=False)
    
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

    def save(self, *args, **kwargs):
        self.calculate_total_hours()
        super().save(*args, **kwargs)

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

    class Meta:
        verbose_name = "حضور ماهانه"
        verbose_name_plural = "حضور ماهانه"
        unique_together = ('employee', 'month')

    def __str__(self):
        return f"{self.employee.username} - {self.month}"