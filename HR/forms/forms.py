from django import forms
from HR.EmployeeAttendanceModel import WeeklyAttendance
from django.contrib.auth.models import User
from HR.EmployeeModel import Employee
from django.utils.translation import gettext_lazy as _
import jdatetime
from datetime import datetime, timedelta

# ویجت سفارشی برای آپلود چندین فایل
class MultipleFileInput(forms.FileInput):
    def __init__(self, attrs=None):
        default_attrs = {'multiple': 'multiple'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)

    def value_from_datadict(self, data, files, name):
        if hasattr(files, 'getlist'):
            return files.getlist(name)
        return files.get(name)

class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput)
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

class WeeklyAttendanceForm(forms.ModelForm):
    approved_by_user1 = forms.ModelChoiceField(
        queryset=Employee.objects.all(),
        required=False,
        label="تایید توسط کارمند 1",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    approved_by_user2 = forms.ModelChoiceField(
        queryset=Employee.objects.all(),
        required=False,
        label="تایید توسط کارمند 2",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    approved_by_user3 = forms.ModelChoiceField(
        queryset=Employee.objects.all(),
        required=False,
        label="تایید توسط کارمند 3",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = WeeklyAttendance
        fields = [
            'week_start_date', 'day', 'saturday_hours', 'sunday_hours', 'description',
            'approved_by_user1', 'approved_by_user2', 'approved_by_user3'
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
    date = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control persian-datepicker',
            'id': 'attendance-date',
            'data-date-format': 'yyyy/mm/dd',
            'autocomplete': 'off',
            'dir': 'ltr'
        }),
        label="تاریخ",
        required=True
    )
    hours = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'id_hours'
        }),
        label="ساعات کاری",
        initial=0
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        required=False,
        label=_("توضیحات")
    )
    documents = forms.FileField(
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*,.pdf,.doc,.docx,.xls,.xlsx'
        }),
        required=False,
        label=_("مستندات")
    )
    approved_by_user1 = forms.ModelChoiceField(
        queryset=Employee.objects.all(),
        required=True,
        label=_("تأیید توسط کارمند ۱"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    approved_by_user2 = forms.ModelChoiceField(
        queryset=Employee.objects.all(),
        required=True,
        label=_("تأیید توسط کارمند ۲"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    approved_by_user3 = forms.ModelChoiceField(
        queryset=Employee.objects.all(),
        required=True,
        label=_("تأیید توسط کارمند ۳"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    day_of_week = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'day-of-week',
            'readonly': 'readonly'
        }),
        required=False,
        label=_("روز هفته")
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            # حذف کارمند فعلی از لیست تاییدکنندگان
            try:
                # ابتدا سعی می‌کنیم کارمند متناظر با کاربر فعلی را پیدا کنیم
                current_employee = Employee.objects.get(user=user)
                # همه کارمندان را می‌گیریم به جز کارمند فعلی
                available_approvers = Employee.objects.exclude(id=current_employee.id)
            except Employee.DoesNotExist:
                # اگر کاربر فعلی کارمند نیست، همه کارمندان را نمایش می‌دهیم
                available_approvers = Employee.objects.all()
                
            self.fields['approved_by_user1'].queryset = available_approvers
            self.fields['approved_by_user2'].queryset = available_approvers
            self.fields['approved_by_user3'].queryset = available_approvers
            
            # توضیحات راهنما برای انتخاب تاییدکنندگان
            self.fields['approved_by_user1'].help_text = "حداقل دو نفر از سه نفر برای تایید نیاز است"
            self.fields['approved_by_user2'].help_text = "افراد متفاوتی را انتخاب کنید"
            self.fields['approved_by_user3'].help_text = "تایید نهایی توسط ادمین انجام می‌شود"

        # تنظیم روز هفته صورت نمی‌گیرد تا کاربر خودش تاریخ را انتخاب کند
        # مترجم روزهای هفته به فارسی - برای استفاده در بخش‌های مختلف
        # شنبه = 6, یکشنبه = 0, دوشنبه = 1, سه‌شنبه = 2, چهارشنبه = 3, پنج‌شنبه = 4, جمعه = 5
        self.weekday_names = {
            2: 'دوشنبه',
            3: 'سه‌شنبه',
            4: 'چهارشنبه', 
            5: 'پنج‌شنبه',
            6: 'جمعه',
            0: 'شنبه',
            1: 'یکشنبه'
        }
        
        # اگر داده‌ای ارسال شده‌است، روز هفته را تعیین کنیم
        if args and args[0]:
            if 'date' in args[0]:
                date_str = args[0].get('date')
                if date_str:
                    try:
                        # جایگزینی جداکننده‌های احتمالی (مانند . یا -)
                        date_str = date_str.replace('.', '/').replace('-', '/').strip()
                        # تبدیل تاریخ جلالی به گرگوری
                        year, month, day = map(int, date_str.split('/'))
                        jalali_date = jdatetime.date(year, month, day)
                        
                        # تنظیم روز هفته
                        self.fields['day_of_week'].initial = self.weekday_names.get(jalali_date.weekday())
                    except (ValueError, IndexError, TypeError):
                        # در صورت خطا در تبدیل تاریخ، روز هفته را تنظیم نمی‌کنیم
                        pass

    def clean(self):
        cleaned_data = super().clean()
        
        # اطمینان از پر شدن فیلد ساعات کاری
        hours = cleaned_data.get('hours')
        if hours is None or hours <= 0:
            self.add_error('hours', "لطفاً ساعات کاری معتبری وارد کنید")
        
        # اطمینان از انتخاب تاییدکنندگان متفاوت
        employee1 = cleaned_data.get('approved_by_user1')
        employee2 = cleaned_data.get('approved_by_user2')
        employee3 = cleaned_data.get('approved_by_user3')
        
        if employee1 and employee2 and employee1.id == employee2.id:
            self.add_error('approved_by_user2', "تاییدکنندگان باید افراد متفاوتی باشند")
        
        if employee1 and employee3 and employee1.id == employee3.id:
            self.add_error('approved_by_user3', "تاییدکنندگان باید افراد متفاوتی باشند")
        
        if employee2 and employee3 and employee2.id == employee3.id:
            self.add_error('approved_by_user3', "تاییدکنندگان باید افراد متفاوتی باشند")
            
        return cleaned_data

    def clean_date(self):
        date_str = self.cleaned_data.get('date')
        if not date_str:
            raise forms.ValidationError("لطفاً یک تاریخ وارد کنید.")

        try:
            # جایگزینی جداکننده‌های احتمالی (مانند . یا -)
            date_str = date_str.replace('.', '/').replace('-', '/').strip()
            # تبدیل رشته به تاریخ جلالی
            year, month, day = map(int, date_str.split('/'))
            jalali_date = jdatetime.date(year, month, day)
            
            # تنظیم روز هفته در cleaned_data
            if hasattr(self, 'weekday_names'):
                self.cleaned_data['day_of_week'] = self.weekday_names.get(jalali_date.weekday())
            
            # اطلاعات اشکال‌زدایی
            print(f"Debug - Form clean_date: Input={date_str}, Parsed jalali_date={jalali_date}")
            
            # مستقیماً تاریخ جلالی را برمی‌گردانیم (نه گرگوری)
            return jalali_date
        except (ValueError, IndexError, TypeError) as e:
            print(f"Debug - Error in clean_date: {str(e)}")
            raise forms.ValidationError(f"لطفاً تاریخ را به فرمت معتبر (مثلاً 1404/02/20) وارد کنید.")
        
        return None