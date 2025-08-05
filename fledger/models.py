from django.db import models
from django.contrib.auth.models import User
from django.forms import ValidationError
from django_jalali.db import models as jmodels
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from bki_barnameh.models.BarnamehModel import Barnameh
from core.CargoProductModel import CargoProduct, VaredKonandeh, Barbary
from django.db.models import Sum, Q, F
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from major.models import Hazinah

class Wallet(models.Model):
    varedkonandeh = models.ForeignKey(VaredKonandeh, on_delete=models.CASCADE, related_name='wallet', verbose_name=_('وارد کننده'))
    description = models.TextField(_('توضیحات'), blank=True, null=True)
    balance = models.BigIntegerField(_('موجودی (ریال)'), default=0)
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
        
        # تمام خریدهایی که کارگو آنها متعلق به این واردکننده است و آدرس ارسال شده باشد
        purchases = Purchase.objects.filter(
            cargo__vared_konandeh=self.varedkonandeh,
            is_canceled=False,
            is_archived=False,
            is_address_sent__in=['1', 'True']  # پشتیبانی از هر دو فرمت برای backward compatibility
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
        
        # محاسبه تراکنش‌های دستی (شامل هزینه‌ها و درآمدها)
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
            is_archived=False,
            is_address_sent__in=['1', 'True']  # پشتیبانی از هر دو فرمت برای backward compatibility
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
        ('Hazinah', _('هزینه')),
        ('Income', _('درآمد'))
    ]
    
    STATUS_CHOICES = [
        ('paid', _('پرداخت شده')),
        ('unpaid', _('پرداخت نشده')),
        ('patially_paid', _('پرداخت جزیی'))
    ]

    PAYMENT_METHOD = [
        ('cash', _('نقدی')),
        ('bank_transfer', _('انتقال بانکی')),
        ('check', _('چک')),
        ('card', _('کارت')),
        ('other', _('سایر'))
    ]

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions', verbose_name=_('کیف پول'), null=True, blank=True)
    transaction_type = models.CharField(_('نوع تراکنش'), max_length=20, choices=TRANSACTION_TYPES)
    amount = models.BigIntegerField(_('مقدار (ریال)'), default=0)
    description = models.TextField(_('توضیحات'), blank=True, null=True)
    file = models.FileField(_('فایل پیوست'), upload_to='fledger_transactions/', blank=True, null=True)
    status = models.CharField(_('وضعیت'), max_length=20, choices=STATUS_CHOICES, default='pending')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_('ایجاد شده توسط'))
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                  related_name='approved_transactions', verbose_name=_('تایید شده توسط'))
    approved_at = jmodels.jDateTimeField(_('تاریخ تایید'), null=True, blank=True)
    created_at = jmodels.jDateTimeField(_('تاریخ ایجاد'), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_('تاریخ بروزرسانی'), auto_now=True)

    hazinah = models.ForeignKey(Hazinah, on_delete=models.CASCADE,
                                related_name='transactions', verbose_name=_('هزینه'),
                                 null=True, blank=True)

    income = models.ForeignKey(Barnameh, on_delete=models.CASCADE,
                                related_name='transactions', verbose_name=_('درآمد'),
                                null=True, blank=True)

    payment_method = models.CharField(_('روش پرداخت'), max_length=20, choices=PAYMENT_METHOD, null=True , blank=True)

    class Meta:
        verbose_name = _('تراکنش')
        verbose_name_plural = _('تراکنش ها')
        ordering = ['-created_at']

    def clean(self):
        super().clean()
    
        if self.transaction_type == 'Hazinah' and not self.hazinah:
            raise ValidationError(_('لطفا هزینه را مشخص کنید.'))
        
        if self.transaction_type == 'Income' and not self.income:
            raise ValidationError(_('لطفا درآمد را مشخص کنید.'))

        if self.income and self.hazinah:
            raise ValidationError(_('لطفا فقط یکی از هزینه و درآمد را مشخص کنید.'))

    def __str__(self):
        return f"{self.wallet.varedkonandeh.name} - {self.get_transaction_type_display()} - {self.amount:,} ریال"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # هنگام تایید تراکنش، کیف پول را بروزرسانی کن
        if self.status == 'approved':
            self.wallet.calculate_balance()

    def approve(self, approved_by_user):
        """تأیید تراکنش"""
        if self.status == 'pending':
            self.status = 'approved'
            self.approved_by = approved_by_user
            from django.utils import timezone
            self.approved_at = timezone.now()
            self.save()
            return True
        return False
    
    def reject(self, rejected_by_user):
        """رد تراکنش"""
        if self.status == 'pending':
            self.status = 'rejected'
            self.approved_by = rejected_by_user
            from django.utils import timezone
            self.approved_at = timezone.now()
            self.save()
            return True
        return False
    
    def cancel(self):
        """لغو تراکنش"""
        if self.status in ['pending', 'approved']:
            self.status = 'cancelled'
            self.save()
            # بروزرسانی کیف پول
            self.wallet.calculate_balance()
            return True
        return False

    


class LedgerEntry(models.Model):
    """
    ثبت دفتر کل برای هر تراکنش خرید
    """
    varedkonandeh = models.ForeignKey(VaredKonandeh, on_delete=models.CASCADE, verbose_name=_('وارد کننده'))
    purchase = models.ForeignKey('core.Purchase', on_delete=models.CASCADE, verbose_name=_('خرید'))
    weight = models.PositiveIntegerField(_('وزن (کیلوگرم)'), default=0)
    price_per_kg = models.PositiveIntegerField(_('فی هر کیلو (ریال)'), default=0)
    total_amount = models.BigIntegerField(_('مبلغ کل (ریال)'), default=0)
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
        
        # بررسی اینکه آیا آدرس ارسال شده است یا نه
        if purchase.is_address_sent not in ['1', 'True']:
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


# سیگنال‌ها برای بروزرسانی خودکار کیف پول‌ها
@receiver(post_save, sender='core.Purchase')
def update_wallet_on_purchase_change(sender, instance, created, **kwargs):
    """
    بروزرسانی کیف پول هنگام ایجاد یا تغییر خرید
    """
    try:
        # بررسی اینکه آیا خرید شرایط لازم را دارد
        if (instance.cargo and 
            instance.cargo.vared_konandeh and 
            not instance.is_canceled and 
            not instance.is_archived and
            instance.is_address_sent in ['1', 'True']):
            
            # ایجاد یا بروزرسانی ثبت دفتر
            LedgerEntry.create_or_update_entry(instance)
            
    except Exception as e:
        # در صورت خطا، آن را لاگ کن اما سیستم را متوقف نکن
        print(f"خطا در بروزرسانی کیف پول برای خرید {instance.id}: {str(e)}")


@receiver(post_delete, sender='core.Purchase')
def cleanup_wallet_on_purchase_delete(sender, instance, **kwargs):
    """
    پاکسازی ثبت‌های دفتر هنگام حذف خرید
    """
    try:
        if instance.cargo and instance.cargo.vared_konandeh:
            # حذف ثبت‌های دفتر مربوط به این خرید
            LedgerEntry.objects.filter(
                varedkonandeh=instance.cargo.vared_konandeh,
                purchase=instance
            ).delete()
            
            # بروزرسانی موجودی کیف پول
            wallet = Wallet.objects.filter(
                varedkonandeh=instance.cargo.vared_konandeh
            ).first()
            if wallet:
                wallet.calculate_balance()
                
    except Exception as e:
        print(f"خطا در پاکسازی ثبت‌های دفتر برای خرید {instance.id}: {str(e)}")


@receiver(post_save, sender=Transaction)
def update_wallet_on_transaction_approve(sender, instance, created, **kwargs):
    """
    بروزرسانی کیف پول هنگام تایید تراکنش
    """
    try:
        if instance.status == 'approved' and not created:
            instance.wallet.calculate_balance()
    except Exception as e:
        print(f"خطا در بروزرسانی کیف پول برای تراکنش {instance.id}: {str(e)}")
    
