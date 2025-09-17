from django import forms
from core.CustomerModel import Customer
from core.SalesAgentModel import SalesAgent
from core.CargoProductModel import CargoProduct
from major.models.NonBazargahProduct import NonBazargahProduct
from core.PurchaseModel import Purchase
from major.models.NonBazargahPurchase import NonBazargahPurchase


class CreatePurchaseForm(forms.Form):
    """
    فرم ایجاد خرید توسط ادمین
    """
    PURCHASE_TYPE_CHOICES = [
        ('', 'انتخاب کنید...'),
        ('bazaargah', 'خرید بازارگاهی'),
        ('non_bazaargah', 'خرید خارج از بازارگاه'),
    ]
    
    # انتخاب نوع خرید
    purchase_type = forms.ChoiceField(
        choices=PURCHASE_TYPE_CHOICES,
        label='نوع خرید',
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_purchase_type',
            'onchange': 'togglePurchaseFields()'
        })
    )
    
    # انتخاب مشتری
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.all(),
        label='مشتری',
        empty_label='انتخاب مشتری...',
        widget=forms.Select(attrs={'class': 'form-control select2'})
    )
    
    # انتخاب کارشناس فروش
    sales_agent = forms.ModelChoiceField(
        queryset=SalesAgent.objects.all(),
        label='کارشناس فروش',
        empty_label='انتخاب کارشناس فروش...',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control select2'})
    )

    # فیلدهای مشترک
    description = forms.CharField(
        label='توضیحات',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'توضیحات اضافی...'
        })
    )

    # فیلدهای مخصوص خرید بازارگاهی
    bazaargah_product = forms.ModelChoiceField(
        queryset=CargoProduct.objects.filter(status=True),
        label='محصول بازارگاه',
        empty_label='انتخاب محصول...',
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control bazaargah-field select2',
            'style': 'display: none;'
        })
    )
    
    bazaargah_weight = forms.IntegerField(
        label='وزن سفارش (کیلوگرم)',
        required=False,
        min_value=1000,
        widget=forms.NumberInput(attrs={
            'class': 'form-control bazaargah-field',
            'style': 'display: none;',
            'placeholder': 'حداقل 1000 کیلوگرم',
            'step': '1'
        })
    )
    
    bazaargah_address = forms.CharField(
        label='آدرس تحویل',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control bazaargah-field',
            'style': 'display: none;',
            'rows': 2,
            'placeholder': 'آدرس کامل تحویل...'
        })
    )

    # فیلدهای مخصوص خرید خارج از بازارگاه
    non_bazaargah_product = forms.ModelChoiceField(
        queryset=NonBazargahProduct.objects.filter(status=True),
        label='محصول خارج از بازارگاه',
        empty_label='انتخاب محصول...',
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control non-bazaargah-field select2',
            'style': 'display: none;'
        })
    )
    
    non_bazaargah_unit = forms.ChoiceField(
        choices=[('', 'انتخاب واحد...')] + NonBazargahPurchase.UNIT_CHOICES,
        label='واحد',
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control non-bazaargah-field select2',
            'style': 'display: none;'
        })
    )
    
    non_bazaargah_quantity = forms.IntegerField(
        label='مقدار',
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control non-bazaargah-field',
            'style': 'display: none;',
            'placeholder': 'مقدار مورد نظر',
            'step': '1'
        })
    )
    
    non_bazaargah_bag_weight = forms.IntegerField(
        label='وزن کیسه (کیلوگرم)',
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control non-bazaargah-field',
            'style': 'display: none;',
            'placeholder': 'در صورت انتخاب واحد کیسه',
            'step': '1'
        })
    )
    
    customer_price = forms.IntegerField(
        label='فی فروش (ریال)',
        required=False,
        min_value=10000,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'قیمت فروش به ریال'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        purchase_type = cleaned_data.get('purchase_type')
        
        if not purchase_type:
            raise forms.ValidationError('نوع خرید الزامی است.')
        
        # اعتبارسنجی فیلدهای بازارگاهی
        if purchase_type == 'bazaargah':
            if not cleaned_data.get('bazaargah_product'):
                raise forms.ValidationError('محصول بازارگاه الزامی است.')
            if not cleaned_data.get('bazaargah_weight'):
                raise forms.ValidationError('وزن سفارش الزامی است.')
        
        # اعتبارسنجی فیلدهای خارج از بازارگاه
        elif purchase_type == 'non_bazaargah':
            if not cleaned_data.get('non_bazaargah_product'):
                raise forms.ValidationError('محصول خارج از بازارگاه الزامی است.')
            if not cleaned_data.get('non_bazaargah_unit'):
                raise forms.ValidationError('واحد الزامی است.')
            if not cleaned_data.get('non_bazaargah_quantity'):
                raise forms.ValidationError('مقدار الزامی است.')
            
            # بررسی وزن کیسه در صورت انتخاب واحد کیسه
            if cleaned_data.get('non_bazaargah_unit') == 'Kiseh' and not cleaned_data.get('non_bazaargah_bag_weight'):
                raise forms.ValidationError('وزن کیسه برای واحد کیسه الزامی است.')
        
        return cleaned_data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # بهبود نمایش فیلدها
        self.fields['customer'].queryset = Customer.objects.select_related().order_by('name')
        self.fields['sales_agent'].queryset = SalesAgent.objects.select_related('user').order_by('name')
        self.fields['bazaargah_product'].queryset = CargoProduct.objects.filter(status=True).order_by('product_type')
        self.fields['non_bazaargah_product'].queryset = NonBazargahProduct.objects.filter(status=True).order_by('name')
