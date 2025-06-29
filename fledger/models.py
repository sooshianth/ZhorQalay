from django.db import models
from django.contrib.auth.models import User
from django_jalali.db import models as jmodels
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from core.CargoProductModel import CargoProduct, VaredKonandeh, Barbary
from django.db.models import Sum, Q, F

class Wallet(models.Model):
    varedkonandeh = models.ForeignKey(VaredKonandeh, on_delete=models.CASCADE, related_name='wallet', verbose_name=_('وارد کننده'))
    description = models.TextField(_('توضیحات'), blank=True, null=True)
    balance = models.DecimalField(_('موجودی (ریال)'), max_digits=15, decimal_places=2, default=0)
    created_at = jmodels.jDateTimeField(_('تاریخ ایجاد'), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_('تاریخ بروزرسانی'), auto_now=True)

    class Meta:
        verbose_name = _('کیف پول')
        verbose_name_plural = _('کیف پول ها')

    def __str__(self):
        return f"{self.varedkonandeh.name} - {self.balance:,} ریال"

    def calculate_balance(self):
        """
        محاسبه موجودی کیف پول بر اساس خریدهای انجام شده
        """
        from core.PurchaseModel import Purchase
        
        total_debt = 0
        
        # تمام خریدهایی که کارگو آنها متعلق به این واردکننده است
        purchases = Purchase.objects.filter(
            cargo__vared_konandeh=self.varedkonandeh,
            is_canceled=False,
            is_archived=False
        )
        
        for purchase in purchases:
            # تعیین وزن بر اساس wallet_index
            if purchase.wallet_index == '0':
                weight = purchase.order_weight or 0
            else:  # wallet_index == '1'
                weight = purchase.delivered_weight or 0
            
            # محاسبه مبلغ: وزن × فی خرید
            if weight > 0 and purchase.company_price > 0:
                amount = weight * purchase.company_price
                total_debt += amount
        
        # محاسبه تراکنش‌های دستی
        manual_transactions = self.transactions.filter(status='approved')
        manual_total = manual_transactions.aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        # موجودی = تراکنش‌های دستی - بدهی‌های محاسبه شده
        self.balance = manual_total - total_debt
        self.save(update_fields=['balance', 'updated_at'])
        
        return self.balance

    def get_purchase_summary(self):
        """
        خلاصه خریدهای مربوط به این واردکننده
        """
        from core.PurchaseModel import Purchase
        
        purchases = Purchase.objects.filter(
            cargo__vared_konandeh=self.varedkonandeh,
            is_canceled=False,
            is_archived=False
        )
        
        summary = {
            'total_purchases': purchases.count(),
            'total_order_weight': 0,
            'total_delivered_weight': 0,
            'total_order_amount': 0,
            'total_delivered_amount': 0,
            'products': {}
        }
        
        for purchase in purchases:
            # جمع آوری آمار کلی
            summary['total_order_weight'] += purchase.order_weight or 0
            summary['total_delivered_weight'] += purchase.delivered_weight or 0
            
            if purchase.order_weight and purchase.company_price:
                summary['total_order_amount'] += purchase.order_weight * purchase.company_price
            
            if purchase.delivered_weight and purchase.company_price:
                summary['total_delivered_amount'] += purchase.delivered_weight * purchase.company_price
            
            # جمع آوری آمار بر اساس محصول
            if purchase.cargo:
                product_key = f"{purchase.cargo.get_product_type_display()} {purchase.cargo.get_country_display()}"
                if product_key not in summary['products']:
                    summary['products'][product_key] = {
                        'count': 0,
                        'total_weight': 0,
                        'total_amount': 0
                    }
                
                summary['products'][product_key]['count'] += 1
                
                if purchase.wallet_index == '0':
                    weight = purchase.order_weight or 0
                else:
                    weight = purchase.delivered_weight or 0
                
                summary['products'][product_key]['total_weight'] += weight
                if weight > 0 and purchase.company_price > 0:
                    summary['products'][product_key]['total_amount'] += weight * purchase.company_price
        
        return summary


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('deposit', _('واریز')),
        ('withdrawal', _('برداشت')),
        ('adjustment', _('تعدیل')),
        ('purchase_debt', _('بدهی خرید')),
    ]
    
    STATUS_CHOICES = [
        ('pending', _('در انتظار تایید')),
        ('approved', _('تایید شده')),
        ('rejected', _('لغو شده')),
    ]

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions', verbose_name=_('کیف پول'))
    transaction_type = models.CharField(_('نوع تراکنش'), max_length=20, choices=TRANSACTION_TYPES, default='deposit')
    amount = models.DecimalField(_('مقدار (ریال)'), max_digits=15, decimal_places=2, default=0)
    description = models.TextField(_('توضیحات'), blank=True, null=True)
    file = models.FileField(_('فایل پیوست'), upload_to='fledger_transactions/', blank=True, null=True)
    status = models.CharField(_('وضعیت'), max_length=20, choices=STATUS_CHOICES, default='pending')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_('ایجاد شده توسط'))
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                  related_name='approved_transactions', verbose_name=_('تایید شده توسط'))
    approved_at = jmodels.jDateTimeField(_('تاریخ تایید'), null=True, blank=True)
    created_at = jmodels.jDateTimeField(_('تاریخ ایجاد'), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_('تاریخ بروزرسانی'), auto_now=True)

    class Meta:
        verbose_name = _('تراکنش')
        verbose_name_plural = _('تراکنش ها')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.wallet.varedkonandeh.name} - {self.get_transaction_type_display()} - {self.amount:,} ریال"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # هنگام تایید تراکنش، کیف پول را بروزرسانی کن
        if self.status == 'approved':
            self.wallet.calculate_balance()


class LedgerEntry(models.Model):
    """
    ثبت دفتر کل برای هر تراکنش خرید
    """
    varedkonandeh = models.ForeignKey(VaredKonandeh, on_delete=models.CASCADE, verbose_name=_('وارد کننده'))
    purchase = models.ForeignKey('core.Purchase', on_delete=models.CASCADE, verbose_name=_('خرید'))
    weight = models.PositiveIntegerField(_('وزن (کیلوگرم)'), default=0)
    price_per_kg = models.PositiveIntegerField(_('فی هر کیلو (ریال)'), default=0)
    total_amount = models.DecimalField(_('مبلغ کل (ریال)'), max_digits=15, decimal_places=2, default=0)
    wallet_index_used = models.CharField(_('شاخص محاسبه'), max_length=1, choices=[('0', 'وزن سفارش'), ('1', 'وزن تحویلی')])
    created_at = jmodels.jDateTimeField(_('تاریخ ایجاد'), auto_now_add=True)
    notes = models.TextField(_('یادداشت'), blank=True, null=True)
    
    class Meta:
        verbose_name = _('ثبت دفتر')
        verbose_name_plural = _('ثبت‌های دفتر')
        unique_together = ['varedkonandeh', 'purchase']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.varedkonandeh.name} - خرید {self.purchase.invoice_id} - {self.total_amount:,} ریال"

    @classmethod
    def create_or_update_entry(cls, purchase):
        """
        ایجاد یا بروزرسانی ثبت دفتر برای یک خرید
        """
        if not purchase.cargo or not purchase.cargo.vared_konandeh:
            return None
            
        # تعیین وزن بر اساس wallet_index
        if purchase.wallet_index == '0':
            weight = purchase.order_weight or 0
        else:
            weight = purchase.delivered_weight or 0
        
        if weight <= 0 or purchase.company_price <= 0:
            return None
            
        total_amount = weight * purchase.company_price
        
        entry, created = cls.objects.update_or_create(
            varedkonandeh=purchase.cargo.vared_konandeh,
            purchase=purchase,
            defaults={
                'weight': weight,
                'price_per_kg': purchase.company_price,
                'total_amount': total_amount,
                'wallet_index_used': purchase.wallet_index,
                'notes': f'محاسبه خودکار بر اساس {"وزن سفارش" if purchase.wallet_index == "0" else "وزن تحویلی"}'
            }
        )
        
        # بروزرسانی کیف پول
        wallet, wallet_created = Wallet.objects.get_or_create(
            varedkonandeh=purchase.cargo.vared_konandeh,
            defaults={'description': f'کیف پول {purchase.cargo.vared_konandeh.name}'}
        )
        wallet.calculate_balance()
        
        return entry
    
