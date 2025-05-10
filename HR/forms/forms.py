from django import forms
from HR.EmployeeAttendanceModel import WeeklyAttendance
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
import jdatetime

class WeeklyAttendanceForm(forms.ModelForm):
    approved_by_user1 = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        label="تایید توسط کاربر 1",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    approved_by_user2 = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        label="تایید توسط کاربر 2",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = WeeklyAttendance
        fields = [
            'week_start_date', 'day', 'saturday_hours', 'sunday_hours', 'description',
            'approved_by_user1', 'approved_by_user2'
        ]
        widgets = {
            'week_start_date': forms.TextInput(attrs={'type': 'text', 'class': 'form-control persian-datepicker'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'week_start_date': 'تاریخ شروع هفته',
            'day': 'روز',
            'description': 'توضیحات',
        }

class DailyAttendanceForm(forms.Form):
    date = forms.DateField(
        widget=forms.TextInput(attrs={
            'class': 'form-control persian-datepicker',
            'id': 'attendance-date',
            'data-date-format': 'yyyy/mm/dd'
        }),
        label="تاریخ",
        input_formats=['%Y/%m/%d']
    )
    hours = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'total-hours-field'
        }),
        label="ساعات کاری",
        initial=0
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        required=False,
        label=_("توضیحات")
    )
    approved_by_user1 = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=True,
        label=_("تأیید توسط کاربر ۱"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    approved_by_user2 = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=True,
        label=_("تأیید توسط کاربر ۲"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['approved_by_user1'].queryset = User.objects.exclude(is_superuser=True).exclude(id=user.id)
            self.fields['approved_by_user2'].queryset = User.objects.exclude(is_superuser=True).exclude(id=user.id)

        # تنظیم مقدار اولیه تاریخ به امروز (تقویم جلالی)
        today = jdatetime.date.today()
        self.fields['date'].widget.attrs['value'] = today.strftime('%Y/%m/%d')

    def clean_date(self):
        date_str = self.cleaned_data.get('date')
        if not date_str:
            raise forms.ValidationError("لطفاً یک تاریخ وارد کنید.")

        # اگر تاریخ به صورت رشته باشد (مانند خروجی persian-datepicker)
        if isinstance(date_str, str):
            try:
                # جایگزینی جداکننده‌های احتمالی (مانند . یا -)
                date_str = date_str.replace('.', '/').replace('-', '/').strip()
                # تبدیل تاریخ جلالی به گرگوری
                jalali_date = jdatetime.date.strptime(date_str, '%Y/%m/%d')
                gregorian_date = jalali_date.togregorian()
                return gregorian_date
            except ValueError:
                raise forms.ValidationError("لطفاً تاریخ را به فرمت معتبر (مثلاً 1404/02/20) وارد کنید.")
        return date_str