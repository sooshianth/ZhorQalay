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
from django.contrib.auth.models import User
from HR.EmployeeAttendanceModel import WeeklyAttendance

class DailyAttendanceForm(forms.Form):
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="تاریخ"
    )
    hours = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label="ساعات کاری"
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        required=False,
        label="توضیحات"
    )
    approved_by_user1 = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=True,
        label="تأیید توسط کاربر ۱",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    approved_by_user2 = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=True,
        label="تأیید توسط کاربر ۲",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['approved_by_user1'].queryset = User.objects.exclude(is_superuser=True).exclude(id=user.id)
            self.fields['approved_by_user2'].queryset = User.objects.exclude(is_superuser=True).exclude(id=user.id)
