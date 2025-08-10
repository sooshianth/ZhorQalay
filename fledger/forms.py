from django import forms
from django.forms import inlineformset_factory
from .models import Transaction, Wallet
from major.models.Hazinah import Hazinah
from major.models.Invoice import Invoice
from major.models.InvoiceItem import InvoiceItem
from core.CargoProductModel import CargoProduct
from major.models.NonBazargahProduct import NonBazargahProduct
from bki_barnameh.models.BarnamehModel import Barnameh


class TransactionForm(forms.ModelForm):
    """
    فرم ایجاد و ویرایش تراکنش
    """
    
    class Meta:
        model = Transaction
        fields = ['wallet', 'transaction_type', 'amount', 'description', 'file', 'hazinah', 'income', 'payment_method']
        
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
        
        self.fields['payment_method'].widget.attrs.update({
            'class': 'form-control-fledger',
        })
        
        self.fields['hazinah'].widget.attrs.update({
            'class': 'form-control-fledger',
        })
        
        self.fields['income'].widget.attrs.update({
            'class': 'form-control-fledger',
        })
        
        # تنظیم لیبل‌ها
        self.fields['wallet'].label = 'کیف پول'
        self.fields['transaction_type'].label = 'نوع تراکنش'
        self.fields['amount'].label = 'مبلغ (ریال)'
        self.fields['description'].label = 'توضیحات'
        self.fields['file'].label = 'فایل ضمیمه'
        self.fields['payment_method'].label = 'روش پرداخت (اختیاری)'
        self.fields['hazinah'].label = 'هزینه (اختیاری)'
        self.fields['income'].label = 'درآمد (اختیاری)'
        
        # تنظیم فیلدهای اختیاری
        self.fields['payment_method'].required = False
        self.fields['hazinah'].required = False
        self.fields['income'].required = False
        
        # تنظیم queryset برای فیلدها
        self.fields['wallet'].queryset = Wallet.objects.select_related('varedkonandeh').all()
        self.fields['hazinah'].queryset = Hazinah.objects.filter(approval_status__in=['approved', 'auto_approved'])
        self.fields['income'].queryset = Barnameh.objects.all()
        
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
        fields = ['transaction_type', 'amount', 'description', 'file', 'hazinah', 'income', 'payment_method']
        
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
        
        self.fields['payment_method'].widget.attrs.update({
            'class': 'form-control-fledger',
        })
        
        self.fields['hazinah'].widget.attrs.update({
            'class': 'form-control-fledger',
        })
        
        self.fields['income'].widget.attrs.update({
            'class': 'form-control-fledger',
        })
        
        # تنظیم فیلدهای اختیاری
        self.fields['file'].required = False
        self.fields['payment_method'].required = False
        self.fields['hazinah'].required = False
        self.fields['income'].required = False
        
        # تنظیم لیبل‌ها
        self.fields['transaction_type'].label = 'نوع تراکنش'
        self.fields['amount'].label = 'مبلغ (ریال)'
        self.fields['description'].label = 'توضیحات (اختیاری)'
        self.fields['file'].label = 'فایل ضمیمه (اختیاری)'
        self.fields['payment_method'].label = 'روش پرداخت (اختیاری)'
        self.fields['hazinah'].label = 'هزینه (اختیاری)'
        self.fields['income'].label = 'درآمد (اختیاری)'
        
        # تنظیم queryset برای فیلدها
        self.fields['hazinah'].queryset = Hazinah.objects.filter(approval_status__in=['approved', 'auto_approved'])
        self.fields['income'].queryset = Barnameh.objects.all()
        
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


class HazinahForm(forms.ModelForm):
    """
    فرم ایجاد و ویرایش هزینه
    """
    
    class Meta:
        model = Hazinah
        fields = [
            'title', 'description', 'cost_type', 'amount', 
            'expense_date', 'due_date', 'tax_amount', 'discount_amount', 
            'priority', 'is_recurring', 'recurring_period', 'attachment'
        ]
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # تنظیم کلاس‌های CSS برای فیلدها
        for field_name, field in self.fields.items():
            if field_name in ['expense_date', 'due_date']:
                field.widget.attrs['class'] = 'form-control-fledger datepicker'
            elif field_name == 'description':
                field.widget.attrs['class'] = 'form-control-fledger'
                field.widget.attrs['rows'] = 3
            else:
                field.widget.attrs['class'] = 'form-control-fledger'
            
        # تنظیمات خاص هر فیلد
        self.fields['title'].widget.attrs.update({
            'placeholder': 'عنوان هزینه',
        })
        
        self.fields['amount'].widget.attrs.update({
            'placeholder': 'مبلغ به ریال',
            'min': '0',
            'step': '1',
            'type': 'number',
        })
        
        self.fields['tax_amount'].widget.attrs.update({
            'placeholder': 'مبلغ مالیات (اختیاری)',
            'min': '0',
            'step': '1',
            'type': 'number',
        })
        
        self.fields['discount_amount'].widget.attrs.update({
            'placeholder': 'مبلغ تخفیف (اختیاری)',
            'min': '0',
            'step': '1',
            'type': 'number',
        })
        
        self.fields['description'].widget.attrs.update({
            'placeholder': 'توضیحات هزینه (اختیاری)',
        })
        
        # تنظیم لیبل‌ها
        self.fields['title'].label = 'عنوان هزینه'
        self.fields['description'].label = 'توضیحات'
        self.fields['cost_type'].label = 'نوع هزینه'
        self.fields['amount'].label = 'مبلغ (ریال)'
        self.fields['expense_date'].label = 'تاریخ هزینه'
        self.fields['due_date'].label = 'سررسید پرداخت (اختیاری)'
        self.fields['tax_amount'].label = 'مبلغ مالیات (اختیاری)'
        self.fields['discount_amount'].label = 'مبلغ تخفیف (اختیاری)'
        self.fields['priority'].label = 'اولویت'
        self.fields['is_recurring'].label = 'هزینه تکراری'
        self.fields['recurring_period'].label = 'دوره تکرار'
        self.fields['attachment'].label = 'فایل پیوست (اختیاری)'
        
        # تنظیم فیلدهای اختیاری
        self.fields['description'].required = False
        self.fields['amount'].required = False  # برای خرید محصول اختیاری است
        self.fields['due_date'].required = False
        self.fields['tax_amount'].required = False
        self.fields['discount_amount'].required = False
        self.fields['recurring_period'].required = False
        self.fields['attachment'].required = False
        
    def clean(self):
        cleaned_data = super().clean()
        cost_type = cleaned_data.get('cost_type')
        amount = cleaned_data.get('amount')
        is_recurring = cleaned_data.get('is_recurring')
        recurring_period = cleaned_data.get('recurring_period')
        
        # برای انواع هزینه غیر از خرید محصول، مبلغ الزامی است
        if cost_type != 'product_purchase' and not amount:
            raise forms.ValidationError('برای این نوع هزینه، وارد کردن مبلغ الزامی است.')
        
        # بررسی دوره تکرار برای هزینه‌های تکراری
        if is_recurring and not recurring_period:
            raise forms.ValidationError('برای هزینه‌های تکراری باید دوره تکرار مشخص شود.')
        
        return cleaned_data
        
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise forms.ValidationError('مبلغ باید بزرگتر از صفر باشد.')
        return amount


class HazinahPaymentForm(forms.Form):
    """
    فرم پرداخت هزینه (ایجاد تراکنش برای هزینه)
    """
    paid_at = forms.DateField(
        label='تاریخ پرداخت',
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control-fledger datepicker', 'type': 'date'})
    )
    
    amount = forms.DecimalField(
        label='مبلغ پرداخت (ریال)',
        max_digits=15,
        decimal_places=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control-fledger',
            'placeholder': 'مبلغ پرداخت',
            'min': '0',
            'step': '1',
        })
    )
    
    description = forms.CharField(
        label='توضیحات (اختیاری)',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control-fledger',
            'rows': 3,
            'placeholder': 'توضیحات پرداخت'
        })
    )
    
    attachment = forms.FileField(
        label='فایل پیوست (اختیاری)',
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control-fledger'})
    )
    
    def __init__(self, *args, **kwargs):
        self.hazinah = kwargs.pop('hazinah', None)
        super().__init__(*args, **kwargs)
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise forms.ValidationError('مبلغ پرداخت باید بزرگتر از صفر باشد.')
        
        # بررسی حداکثر مبلغ قابل پرداخت
        if self.hazinah:
            remaining_amount = self.hazinah.remaining_amount
            if amount > remaining_amount:
                raise forms.ValidationError(f'مبلغ پرداخت نمی‌تواند بیشتر از مبلغ باقی‌مانده ({remaining_amount:,} ریال) باشد.')
        
        return amount


class InvoiceForm(forms.ModelForm):
    """
    فرم ایجاد و ویرایش فاکتور
    """
    
    class Meta:
        model = Invoice
        fields = ['invoice_id', 'issue_date', 'description', 'attachment']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # تنظیم کلاس‌های CSS برای فیلدها
        for field_name, field in self.fields.items():
            if field_name == 'issue_date':
                field.widget.attrs['class'] = 'form-control-fledger datepicker'
            elif field_name == 'description':
                field.widget.attrs['class'] = 'form-control-fledger'
                field.widget.attrs['rows'] = 3
            else:
                field.widget.attrs['class'] = 'form-control-fledger'
        
        # تنظیم لیبل‌ها
        self.fields['invoice_id'].label = 'شماره فاکتور'
        self.fields['issue_date'].label = 'تاریخ صدور (اختیاری)'
        self.fields['description'].label = 'توضیحات (اختیاری)'
        self.fields['attachment'].label = 'فایل پیوست (اختیاری)'
        
        # تنظیم فیلدهای اختیاری
        self.fields['issue_date'].required = False
        self.fields['description'].required = False
        self.fields['attachment'].required = False
        
        # تنظیم placeholder
        self.fields['invoice_id'].widget.attrs.update({
            'placeholder': 'شماره فاکتور',
        })
        self.fields['description'].widget.attrs.update({
            'placeholder': 'توضیحات فاکتور (اختیاری)',
        })


class InvoiceItemForm(forms.ModelForm):
    """
    فرم ایجاد و ویرایش آیتم فاکتور
    """
    
    class Meta:
        model = InvoiceItem
        fields = ['product_type', 'cargo_product', 'non_bazargah_product', 'price', 'amount']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # تنظیم کلاس‌های CSS برای فیلدها
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control-fledger'
        
        # تنظیم لیبل‌ها
        self.fields['product_type'].label = 'نوع محصول'
        self.fields['cargo_product'].label = 'محصول بازارگاه (اختیاری)'
        self.fields['non_bazargah_product'].label = 'محصول غیر بازارگاه (اختیاری)'
        self.fields['price'].label = 'قیمت واحد (ریال)'
        self.fields['amount'].label = 'مقدار'
        
        # تنظیم فیلدهای اختیاری
        self.fields['cargo_product'].required = False
        self.fields['non_bazargah_product'].required = False
        
        # تنظیم queryset برای محصولات
        self.fields['cargo_product'].queryset = CargoProduct.objects.all()
        self.fields['non_bazargah_product'].queryset = NonBazargahProduct.objects.all()
        
        # تنظیم placeholder و ویژگی‌های فیلدها
        self.fields['price'].widget.attrs.update({
            'placeholder': 'قیمت واحد',
            'min': '0',
            'step': '1',
            'type': 'number',
        })
        
        self.fields['amount'].widget.attrs.update({
            'placeholder': 'مقدار',
            'min': '0',
            'step': '1',
            'type': 'number',
        })
    
    def clean(self):
        cleaned_data = super().clean()
        product_type = cleaned_data.get('product_type')
        cargo_product = cleaned_data.get('cargo_product')
        non_bazargah_product = cleaned_data.get('non_bazargah_product')
        
        # بررسی انتخاب محصول بر اساس نوع
        if product_type == 'Bazargah' and not cargo_product:
            raise forms.ValidationError('برای محصول بازارگاهی باید محصول بازارگاه انتخاب شود.')
        
        if product_type == 'NonBazargah' and not non_bazargah_product:
            raise forms.ValidationError('برای محصول غیر بازارگاهی باید محصول غیر بازارگاه انتخاب شود.')
        
        # بررسی اینکه فقط یکی از محصولات انتخاب شده باشد
        if cargo_product and non_bazargah_product:
            raise forms.ValidationError('لطفاً فقط یکی از انواع محصولات را انتخاب کنید.')
        
        return cleaned_data


# ایجاد InlineFormSet برای آیتم‌های فاکتور
InvoiceItemFormSet = inlineformset_factory(
    Invoice, 
    InvoiceItem, 
    form=InvoiceItemForm,
    extra=1,  # فقط یک فرم خالی اضافی نمایش داده می‌شود
    min_num=1,  # حداقل یک آیتم لازم است
    max_num=10,  # حداکثر 10 آیتم مجاز
    can_delete=True,  # امکان حذف آیتم‌ها
    validate_min=True
)