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
        help_text=_("فایل اکسل حاوی شماره تلفن‌ها و اطلاعات اضافی")
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
        """استخراج شماره تلفن‌ها و اطلاعات اضافی از فایل اکسل یا متن وارد شده"""
        cleaned_data = self.cleaned_data
        excel_file = cleaned_data.get('excel_file')
        phone_numbers_text = cleaned_data.get('phone_numbers')
        
        if excel_file:
            try:
                df = pd.read_excel(excel_file)
                # بررسی وجود ستون‌های مورد نیاز
                if df.empty:
                    raise forms.ValidationError("فایل اکسل خالی است")
                
                # اگر فقط یک ستون وجود دارد، فرض می‌کنیم شماره تلفن است
                if len(df.columns) == 1:
                    phone_numbers = df.iloc[:, 0].astype(str).tolist()
                    # ایجاد دیکشنری با شماره‌ها و مقادیر خالی برای فیلدهای دیگر
                    phone_data = []
                    for number in phone_numbers:
                        if number and str(number).strip() != 'nan':
                            phone_data.append({
                                'phone_number': number,
                                'customer_name': '',
                                'sub_branch': '',
                                'sub_branch_phone': '',
                                'city': '',
                                'user_type': ''
                            })
                    return phone_data
                
                # اگر چندین ستون وجود دارد، سعی می‌کنیم ستون‌ها را شناسایی کنیم
                else:
                    phone_data = []
                    # بررسی ستون شماره تلفن (ستون اول یا ستونی که شامل شماره است)
                    phone_column = None
                    for i, col in enumerate(df.columns):
                        col_str = str(col).lower()
                        if any(keyword in col_str for keyword in ['شماره', 'تلفن', 'phone', 'number', 'mobile']):
                            phone_column = i
                            break
                    
                    if phone_column is None:
                        phone_column = 0  # اگر ستون مشخص نشد، ستون اول را در نظر می‌گیریم
                    
                    # بررسی ستون‌های دیگر
                    customer_name_col = None
                    sub_branch_col = None
                    sub_branch_phone_col = None
                    city_col = None
                    user_type_col = None
                    
                    for i, col in enumerate(df.columns):
                        col_str = str(col).lower()
                        if any(keyword in col_str for keyword in ['نام', 'مشتری', 'customer', 'name']):
                            customer_name_col = i
                        elif any(keyword in col_str for keyword in ['زیر', 'مجموعه', 'sub', 'branch']):
                            sub_branch_col = i
                        elif any(keyword in col_str for keyword in ['شماره', 'زیر', 'مجموعه', 'sub', 'phone']):
                            if i != phone_column:  # اطمینان از اینکه همان ستون شماره تلفن نیست
                                sub_branch_phone_col = i
                        elif any(keyword in col_str for keyword in ['شهر', 'city']):
                            city_col = i
                        elif any(keyword in col_str for keyword in ['نوع', 'کاربری', 'user', 'type']):
                            user_type_col = i
                    
                    # استخراج داده‌ها
                    for index, row in df.iterrows():
                        phone_number = str(row.iloc[phone_column]).strip()
                        if phone_number and phone_number != 'nan':
                            phone_data.append({
                                'phone_number': phone_number,
                                'customer_name': str(row.iloc[customer_name_col]).strip() if customer_name_col is not None and str(row.iloc[customer_name_col]) != 'nan' else '',
                                'sub_branch': str(row.iloc[sub_branch_col]).strip() if sub_branch_col is not None and str(row.iloc[sub_branch_col]) != 'nan' else '',
                                'sub_branch_phone': str(row.iloc[sub_branch_phone_col]).strip() if sub_branch_phone_col is not None and str(row.iloc[sub_branch_phone_col]) != 'nan' else '',
                                'city': str(row.iloc[city_col]).strip() if city_col is not None and str(row.iloc[city_col]) != 'nan' else '',
                                'user_type': str(row.iloc[user_type_col]).strip() if user_type_col is not None and str(row.iloc[user_type_col]) != 'nan' else ''
                            })
                    
                    return phone_data
                    
            except Exception as e:
                raise forms.ValidationError(f"خطا در خواندن فایل اکسل: {str(e)}")
        
        # استخراج از متن کپی پیست شده
        elif phone_numbers_text:
            lines = phone_numbers_text.strip().split('\n')
            phone_data = []
            for line in lines:
                if line.strip():
                    phone_data.append({
                        'phone_number': line.strip(),
                        'customer_name': '',
                        'sub_branch': '',
                        'sub_branch_phone': '',
                        'city': '',
                        'user_type': ''
                    })
            return phone_data
        
        return []
    
    def clean_phone_data(self, phone_data):
        """تمیز کردن و اعتبارسنجی داده‌های شماره تلفن"""
        cleaned_data = []
        
        for item in phone_data:
            phone_number = item['phone_number']
            
            # تبدیل اعداد فارسی به انگلیسی
            persian_digits = "۰۱۲۳۴۵۶۷۸۹"
            english_digits = "0123456789"
            translation_table = str.maketrans(persian_digits, english_digits)
            phone_number = str(phone_number).translate(translation_table)
            
            # حذف کاراکترهای غیر عدد
            phone_number = ''.join(c for c in phone_number if c.isdigit())
            
            # استاندارد کردن فرمت شماره (حذف صفر ابتدایی)
            if phone_number.startswith('0'):
                phone_number = phone_number[1:]
                
            # بررسی معتبر بودن شماره
            if phone_number.startswith('9') and len(phone_number) == 10:
                cleaned_item = item.copy()
                cleaned_item['phone_number'] = phone_number
                cleaned_data.append(cleaned_item)
        
        return cleaned_data
        
class PhoneAssignmentForm(forms.ModelForm):
    """فرم تک شماره تلفن برای کارشناس فروش"""
    class Meta:
        model = PhoneAssignment
        fields = ['phone_number', 'sales_agent', 'notes', 'customer_name', 'sub_branch', 'sub_branch_phone', 'city', 'user_type'] 