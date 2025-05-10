from django import forms
from HR.EmployeeAttendanceModel import WeeklyAttendance
from django.contrib.auth.models import User

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
            'week_start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'week_start_date': 'تاریخ شروع هفته',
            'day': 'روز',
            'description': 'توضیحات',
        }

from django import forms
from HR.EmployeeAttendanceModel import WeeklyAttendance
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
import jdatetime

class DailyAttendanceForm(forms.Form):
    date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date', 
            'class': 'form-control',
            'id': 'attendance-date'
        }),
        label="تاریخ",
        input_formats=['%Y-%m-%d']
    )
    hours = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'readonly': 'readonly',
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
        
        # مقداردهی اولیه تاریخ به امروز در تقویم جلالی
        today = jdatetime.date.today()
        self.fields['date'].initial = today.strftime('%Y-%m-%d')
