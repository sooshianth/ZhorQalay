from django import forms
from .models import Transaction, Wallet


class TransactionForm(forms.ModelForm):
    """
    فرم ایجاد و ویرایش تراکنش
    """
    
    class Meta:
        model = Transaction
        fields = ['wallet', 'transaction_type', 'amount', 'description', 'file']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # تنظیم کلاس‌های CSS برای فیلدها
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control-fledger'
            
        # تنظیمات خاص هر فیلد
        self.fields['wallet'].widget.attrs.update({
            'class': 'form-control-fledger',
        })
        
        self.fields['transaction_type'].widget.attrs.update({
            'class': 'form-control-fledger',
        })
        
        self.fields['amount'].widget.attrs.update({
            'class': 'form-control-fledger',
            'placeholder': 'مبلغ به ریال',
            'min': '0',
            'step': '1',
            'type': 'number',
        })
        
        self.fields['description'].widget.attrs.update({
            'class': 'form-control-fledger',
            'placeholder': 'توضیحات تراکنش (اختیاری)',
            'rows': 3,
        })
        
        self.fields['file'].widget.attrs.update({
            'class': 'form-control-fledger',
        })
        
        # تنظیم لیبل‌ها
        self.fields['wallet'].label = 'کیف پول'
        self.fields['transaction_type'].label = 'نوع تراکنش'
        self.fields['amount'].label = 'مبلغ (ریال)'
        self.fields['description'].label = 'توضیحات'
        self.fields['file'].label = 'فایل ضمیمه'
        
        # تنظیم queryset برای wallet
        self.fields['wallet'].queryset = Wallet.objects.select_related('varedkonandeh').all()
        
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None:
            try:
                amount = int(amount)
                if amount <= 0:
                    raise forms.ValidationError('مبلغ باید بزرگتر از صفر باشد.')
                if amount > 999999999999:  # محدودیت برای مبالغ خیلی بزرگ
                    raise forms.ValidationError('مبلغ وارد شده خیلی بزرگ است.')
                return amount
            except (ValueError, TypeError):
                raise forms.ValidationError('لطفاً یک عدد صحیح وارد کنید.')
        return amount


class TransactionEditForm(forms.ModelForm):
    """
    فرم ویرایش تراکنش (بدون فیلد wallet)
    """
    
    class Meta:
        model = Transaction
        fields = ['transaction_type', 'amount', 'description', 'file']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # تنظیم کلاس‌های CSS برای فیلدها
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control-fledger'
            
        # تنظیمات خاص هر فیلد
        self.fields['transaction_type'].widget.attrs.update({
            'class': 'form-control-fledger',
        })
        
        self.fields['amount'].widget.attrs.update({
            'class': 'form-control-fledger',
            'placeholder': 'مبلغ به ریال',
            'step': '1',
            'type': 'number',
        })
        
        self.fields['description'].widget.attrs.update({
            'class': 'form-control-fledger',
            'placeholder': 'توضیحات تراکنش (اختیاری)',
            'rows': 3,
        })
        
        self.fields['description'].required = False
        
        self.fields['file'].widget.attrs.update({
            'class': 'form-control-fledger',
        })
        
        self.fields['file'].required = False
        
        # تنظیم لیبل‌ها
        self.fields['transaction_type'].label = 'نوع تراکنش'
        self.fields['amount'].label = 'مبلغ (ریال)'
        self.fields['description'].label = 'توضیحات (اختیاری)'
        self.fields['file'].label = 'فایل ضمیمه (اختیاری)'
        
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None:
            try:
                amount = int(amount)
                if amount <= 0:
                    raise forms.ValidationError('مبلغ باید بزرگتر از صفر باشد.')
                if amount > 999999999999:  # محدودیت برای مبالغ خیلی بزرگ
                    raise forms.ValidationError('مبلغ وارد شده خیلی بزرگ است.')
                return amount
            except (ValueError, TypeError):
                raise forms.ValidationError('لطفاً یک عدد صحیح وارد کنید.')
        return amount 