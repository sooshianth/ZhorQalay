from django import forms
from django.utils.translation import gettext_lazy as _
from core.SalesAgentModel import SalesAgent
from core.SalesAgentModel import PhoneAssignment
import pandas as pd

class PhoneImportForm(forms.Form):
    """فرم آپلود شماره تلفن با اکسل یا کپی پیست"""
    sales_agent = forms.ModelChoiceField(
        queryset=SalesAgent.objects.all(),
        label=_("کارشناس فروش")
    )
    
    # برای آپلود فایل اکسل
    excel_file = forms.FileField(
        required=False,
        label=_("فایل اکسل"),
        help_text=_("فایل اکسل حاوی شماره تلفن‌ها (ستون A)")
    )
    
    # برای کپی پیست شماره‌ها
    phone_numbers = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 10, 'placeholder': '09123456789\n09123456788\n...'}),
        label=_("شماره‌های تلفن"),
        help_text=_("هر شماره تلفن را در یک خط وارد کنید")
    )
    
    def clean(self):
        cleaned_data = super().clean()
        excel_file = cleaned_data.get('excel_file')
        phone_numbers = cleaned_data.get('phone_numbers')
        
        if not excel_file and not phone_numbers:
            raise forms.ValidationError(_("لطفاً یا فایل اکسل آپلود کنید یا شماره‌ها را وارد کنید"))
            
        return cleaned_data
    
    def extract_phone_numbers(self):
        """استخراج شماره تلفن‌ها از فایل اکسل یا متن وارد شده"""
        cleaned_data = self.cleaned_data
        excel_file = cleaned_data.get('excel_file')
        phone_numbers_text = cleaned_data.get('phone_numbers')
        phone_numbers = []
        
        # استخراج از فایل اکسل
        if excel_file:
            try:
                df = pd.read_excel(excel_file)
                # فرض می‌کنیم شماره‌ها در ستون اول هستند
                numbers = df.iloc[:, 0].astype(str).tolist()
                phone_numbers.extend(numbers)
            except Exception as e:
                raise forms.ValidationError(f"خطا در خواندن فایل اکسل: {str(e)}")
        
        # استخراج از متن کپی پیست شده
        elif phone_numbers_text:
            lines = phone_numbers_text.strip().split('\n')
            phone_numbers.extend([line.strip() for line in lines if line.strip()])
        
        # پردازش و تمیز کردن شماره‌ها
        cleaned_numbers = []
        for number in phone_numbers:
            # تبدیل اعداد فارسی به انگلیسی
            persian_digits = "۰۱۲۳۴۵۶۷۸۹"
            english_digits = "0123456789"
            translation_table = str.maketrans(persian_digits, english_digits)
            number = str(number).translate(translation_table)
            
            # حذف کاراکترهای غیر عدد
            number = ''.join(c for c in number if c.isdigit())
            
            # استاندارد کردن فرمت شماره (حذف صفر ابتدایی)
            if number.startswith('0'):
                number = number[1:]
                
            # بررسی معتبر بودن شماره
            if number.startswith('9') and len(number) == 10:
                cleaned_numbers.append(number)
        
        return cleaned_numbers
        
class PhoneAssignmentForm(forms.ModelForm):
    """فرم تک شماره تلفن برای کارشناس فروش"""
    class Meta:
        model = PhoneAssignment
        fields = ['phone_number', 'sales_agent', 'notes'] 