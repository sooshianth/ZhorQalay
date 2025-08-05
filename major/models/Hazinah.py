from django.db import models
from django_jalali.db import models as jmodels
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from .NonBazargahProduct import NonBazargahProduct

class Hazinah(models.Model):
    """
    مدل هزینه برای کنترل تمام هزینه‌های شرکت
    """
    
    COST_TYPES = [
        ('product_purchase', 'خرید محصول'),
        ('transportation', 'کرایه و حمل‌ونقل'),
        ('overhead', 'هزینه‌های سربار'),
        ('maintenance', 'تعمیر و نگهداری'),
        ('salary', 'حقوق و دستمزد'),
        ('utilities', 'آب، برق، گاز'),
        ('rent', 'اجاره'),
        ('insurance', 'بیمه'),
        ('marketing', 'بازاریابی و تبلیغات'),
        ('legal', 'هزینه‌های حقوقی'),
        ('tax', 'مالیات'),
        ('bank_charges', 'کارمزد بانکی'),
        ('fuel', 'سوخت'),
        ('packaging', 'بسته‌بندی'),
        ('storage', 'انبارداری'),
        ('communication', 'ارتباطات'),
        ('office_supplies', 'لوازم اداری'),
        ('training', 'آموزش'),
        ('consulting', 'مشاوره'),
        ('other', 'سایر')
    ]
    
    APPROVAL_STATUS = [
        ('pending', 'در انتظار تأیید'),
        ('approved', 'تأیید شده'),
        ('rejected', 'رد شده'),
        ('auto_approved', 'تأیید خودکار')
    ]
    
    PAYMENT_STATUS = [
        ('unpaid', 'پرداخت نشده'),
        ('paid', 'پرداخت شده'),
        ('partial', 'پرداخت جزئی'),
        ('cancelled', 'لغو شده')
    ]
    
    # اطلاعات اصلی هزینه
    title = models.CharField(_('عنوان هزینه'), max_length=200)
    description = models.TextField(_('توضیحات'), blank=True, null=True)
    cost_type = models.CharField(_('نوع هزینه'), max_length=30, choices=COST_TYPES)
    amount = models.DecimalField(_('مبلغ (ریال)'), max_digits=15, decimal_places=0)
    
    # ارتباط با محصولات (در صورت نیاز)
    cargo_product = models.ForeignKey(
        'core.CargoProduct',
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        verbose_name=_('محصول بازارگاه'),
        help_text=_('در صورتی که هزینه مربوط به محصول بازارگاه است')
    )
    
    non_bazargah_product = models.ForeignKey(
        NonBazargahProduct,
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        verbose_name=_('محصول خارج از بازارگاه'),
        help_text=_('در صورتی که هزینه مربوط به محصول خارج از بازارگاه است')
    )
    
    # اطلاعات تأیید
    approval_status = models.CharField(
        _('وضعیت تأیید'), 
        max_length=20, 
        choices=APPROVAL_STATUS, 
        default='pending'
    )
    approved_by = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='approved_costs',
        verbose_name=_('تأیید کننده')
    )
    approval_date = jmodels.jDateTimeField(_('تاریخ تأیید'), null=True, blank=True)
    approval_notes = models.TextField(_('یادداشت تأیید'), blank=True, null=True)

    # اطلاعات مالی اضافی
    tax_amount = models.DecimalField(
        _('مبلغ مالیات'), 
        max_digits=15, 
        decimal_places=0, 
        default=0,
        help_text=_('مبلغ مالیات در صورت وجود')
    )
    discount_amount = models.DecimalField(
        _('مبلغ تخفیف'), 
        max_digits=15, 
        decimal_places=0, 
        default=0
    )
    final_amount = models.DecimalField(
        _('مبلغ نهایی'), 
        max_digits=15, 
        decimal_places=0, 
        blank=True, 
        null=True
    )
    
    # اطلاعات زمانی
    expense_date = jmodels.jDateField(_('تاریخ هزینه'), help_text=_('تاریخ واقعی انجام هزینه'))
    due_date = jmodels.jDateField(_('سررسید پرداخت'), blank=True, null=True)
    created_at = jmodels.jDateTimeField(_('تاریخ ثبت'), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_('تاریخ آخرین بروزرسانی'), auto_now=True)
    created_by = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='created_costs',
        verbose_name=_('ثبت کننده')
    )
    
    # اطلاعات اضافی
    is_recurring = models.BooleanField(_('هزینه تکراری'), default=False)
    recurring_period = models.CharField(
        _('دوره تکرار'), 
        max_length=20, 
        blank=True, 
        null=True,
        choices=[
            ('daily', 'روزانه'),
            ('weekly', 'هفتگی'),
            ('monthly', 'ماهانه'),
            ('quarterly', 'سه‌ماهه'),
            ('yearly', 'سالانه')
        ]
    )
    priority = models.CharField(
        _('اولویت'), 
        max_length=10, 
        choices=[
            ('low', 'پایین'),
            ('medium', 'متوسط'),
            ('high', 'بالا'),
            ('urgent', 'فوری')
        ],
        default='medium'
    )
    
    # فایل پیوست (فاکتور، رسید و غیره)
    attachment = models.FileField(
        _('فایل پیوست'), 
        upload_to='cost_attachments/%Y/%m/', 
        blank=True, 
        null=True
    )
    
    class Meta:
        verbose_name = _('هزینه')
        verbose_name_plural = _('هزینه‌ها')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['cost_type']),
            models.Index(fields=['approval_status']),
            models.Index(fields=['expense_date']),
            models.Index(fields=['created_at']),
        ]
    
    def clean(self):
        """اعتبارسنجی داده‌ها"""
        super().clean()
        
        # بررسی انتخاب محصول
        if self.cargo_product and self.non_bazargah_product:
            raise ValidationError({
                'cargo_product': _('نمی‌توانید هم‌زمان هر دو نوع محصول را انتخاب کنید.'),
                'non_bazargah_product': _('نمی‌توانید هم‌زمان هر دو نوع محصول را انتخاب کنید.')
            })
        
        # اگر نوع هزینه "خرید محصول" است، باید یکی از محصولات انتخاب شود
        if self.cost_type == 'product_purchase' and not (self.cargo_product or self.non_bazargah_product):
            raise ValidationError({
                'cargo_product': _('برای هزینه خرید محصول، انتخاب محصول اجباری است.'),
                'non_bazargah_product': _('برای هزینه خرید محصول، انتخاب محصول اجباری است.')
            })
        
        # بررسی مبلغ
        if self.amount <= 0:
            raise ValidationError({
                'amount': _('مبلغ باید بیشتر از صفر باشد.')
            })
        
        # بررسی تاریخ سررسید
        if self.due_date and self.expense_date and self.due_date < self.expense_date:
            raise ValidationError({
                'due_date': _('تاریخ سررسید نمی‌تواند قبل از تاریخ هزینه باشد.')
            })
        
        # بررسی هزینه تکراری
        if self.is_recurring and not self.recurring_period:
            raise ValidationError({
                'recurring_period': _('برای هزینه تکراری، دوره تکرار باید مشخص شود.')
            })
        
        # اگر مبلغ تخفیف یا مالیات بیشتر از مبلغ اصلی باشد
        if self.discount_amount > self.amount:
            raise ValidationError({
                'discount_amount': _('مبلغ تخفیف نمی‌تواند بیشتر از مبلغ اصلی باشد.')
            })
    
    def save(self, *args, **kwargs):
        """ذخیره با محاسبه مبلغ نهایی و تأیید خودکار"""
        from django.utils import timezone
        
        # محاسبه مبلغ نهایی
        self.final_amount = self.amount + self.tax_amount - self.discount_amount

        AUTO_APPROVAL_THRESHOLD = Decimal('100000000')  
        
        if (self.approval_status == 'pending' and 
            self.final_amount < AUTO_APPROVAL_THRESHOLD):
            self.approval_status = 'auto_approved'
            self.approval_date = timezone.now()
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        product_info = ""
        if self.cargo_product:
            product_info = f" - {self.cargo_product}"
        elif self.non_bazargah_product:
            product_info = f" - {self.non_bazargah_product}"
        
        return f"{self.get_cost_type_display()} - {self.title} - {self.amount:,} ریال{product_info}"
    
    @property
    def related_product(self):
        """برگرداندن محصول مرتبط (هر کدام که انتخاب شده باشد)"""
        return self.cargo_product or self.non_bazargah_product
    
    @property 
    def product_type_display(self):
        """نمایش نوع محصول مرتبط"""
        if self.cargo_product:
            return "بازارگاه"
        elif self.non_bazargah_product:
            return "خارج از بازارگاه"
        return "بدون محصول"
    
    @property
    def payment_status(self):
        """محاسبه وضعیت پرداخت بر اساس تراکنش‌ها"""
        transactions = self.transactions.filter(status='approved')
        
        if not transactions.exists():
            return 'unpaid'
        
        # برای هزینه‌ها، تراکنش‌ها منفی هستند (amount < 0)
        total_paid = sum(abs(transaction.amount) for transaction in transactions if transaction.amount < 0)
        # اگر تراکنش مثبت باشد (مثل برگشت) از کل کم می‌شود
        total_refunded = sum(transaction.amount for transaction in transactions if transaction.amount > 0)
        net_paid = total_paid - total_refunded
        
        if net_paid <= 0:
            return 'unpaid'
        elif net_paid >= self.final_amount:
            return 'paid'
        else:
            return 'partial'
    
    @property
    def total_transactions_amount(self):
        """محاسبه مجموع مبلغ تراکنش‌های تأیید شده"""
        transactions = self.transactions.filter(status='approved')
        # برای هزینه‌ها، تراکنش‌ها منفی هستند (amount < 0)
        total_paid = sum(abs(transaction.amount) for transaction in transactions if transaction.amount < 0)
        # اگر تراکنش مثبت باشد (مثل برگشت) از کل کم می‌شود
        total_refunded = sum(transaction.amount for transaction in transactions if transaction.amount > 0)
        return total_paid - total_refunded
    
    @property
    def remaining_amount(self):
        """محاسبه مبلغ باقی‌مانده"""
        return max(0, self.final_amount - self.total_transactions_amount)
    
    @property
    def has_transactions(self):
        """آیا این هزینه تراکنش دارد؟"""
        return self.transactions.exists()
    
    @property
    def approved_transactions(self):
        """تراکنش‌های تأیید شده"""
        return self.transactions.filter(status='approved')
    
    @property
    def pending_transactions(self):
        """تراکنش‌های در انتظار تأیید"""
        return self.transactions.filter(status='pending')
    
    def get_cost_type_display(self):
        """نمایش نوع هزینه به صورت کاربرپسند"""
        return dict(self.COST_TYPES).get(self.cost_type, _('نامشخص'))

    def get_approval_status_display_color(self):
        """رنگ وضعیت تأیید برای نمایش در قالب"""
        colors = {
            'pending': 'warning',
            'approved': 'success',
            'rejected': 'danger',
            'auto_approved': 'info'
        }
        return colors.get(self.approval_status, 'secondary')
    
    def get_payment_status_display_color(self):
        """رنگ وضعیت پرداخت برای نمایش در قالب"""
        colors = {
            'unpaid': 'danger',
            'paid': 'success',
            'partial': 'warning',
            'cancelled': 'secondary'
        }
        return colors.get(self.payment_status, 'secondary')
    
    def can_be_approved(self):
        """آیا این هزینه قابل تأیید است؟"""
        return self.approval_status == 'pending'
    
    def can_be_paid(self):
        """آیا این هزینه قابل پرداخت است؟"""
        return (self.approval_status in ['approved', 'auto_approved'] and 
                self.payment_status in ['unpaid', 'partial'])
    
    def approve(self, approved_by_user, notes=None):
        """تأیید هزینه"""
        from django.utils import timezone
        
        if self.can_be_approved():
            self.approval_status = 'approved'
            self.approved_by = approved_by_user
            self.approval_date = timezone.now()
            if notes:
                self.approval_notes = notes
            self.save()
            return True
        return False
    
    def reject(self, rejected_by_user, notes=None):
        """رد هزینه"""
        from django.utils import timezone
        
        if self.can_be_approved():
            self.approval_status = 'rejected'
            self.approved_by = rejected_by_user
            self.approval_date = timezone.now()
            if notes:
                self.approval_notes = notes
            self.save()
            return True
        return False
    
    def create_payment_transaction(self, amount, wallet, payment_method=None, payment_reference=None, created_by=None, description=None):
        """ایجاد تراکنش پرداخت برای این هزینه"""
        from fledger.models import Transaction
        
        if not self.can_be_paid():
            return None, "این هزینه قابل پرداخت نیست"
        
        if amount <= 0:
            return None, "مبلغ باید بیشتر از صفر باشد"
        
        if amount > self.remaining_amount:
            return None, "مبلغ نمی‌تواند بیشتر از مبلغ باقی‌مانده باشد"
        
        # ایجاد تراکنش
        transaction = Transaction.objects.create(
            wallet=wallet,
            transaction_type='Hazinah',
            amount=-amount,  # منفی چون هزینه است
            hazinah=self,
            payment_method=payment_method,
            description=description or f"پرداخت هزینه: {self.title}",
            created_by=created_by,
            status='pending'  # در انتظار تأیید
        )
        
        return transaction, "تراکنش با موفقیت ایجاد شد"
    
    def get_payment_history(self):
        """تاریخچه پرداخت‌های این هزینه"""
        return self.transactions.all().order_by('-created_at')
    
    def get_payment_summary(self):
        """خلاصه وضعیت پرداخت"""
        transactions = self.transactions.filter(status='approved')
        
        summary = {
            'total_transactions': transactions.count(),
            'total_paid': 0,
            'total_refunded': 0,
            'net_paid': 0,
            'remaining': self.remaining_amount,
            'payment_status': self.payment_status,
            'last_payment_date': None
        }
        
        for transaction in transactions:
            if transaction.amount < 0:  # هزینه (منفی)
                summary['total_paid'] += abs(transaction.amount)
            else:  # برگشت (مثبت)
                summary['total_refunded'] += transaction.amount
                
            if not summary['last_payment_date'] or transaction.approved_at > summary['last_payment_date']:
                summary['last_payment_date'] = transaction.approved_at
        
        summary['net_paid'] = summary['total_paid'] - summary['total_refunded']
        
        return summary
    
    @classmethod
    def get_pending_approvals(cls):
        """هزینه‌های در انتظار تأیید"""
        return cls.objects.filter(approval_status='pending')
    
    @classmethod
    def get_approved_unpaid(cls):
        """هزینه‌های تأیید شده ولی پرداخت نشده یا جزئی"""
        expenses = cls.objects.filter(
            approval_status__in=['approved', 'auto_approved']
        )
        # فیلتر کردن بر اساس وضعیت پرداخت محاسبه شده
        unpaid_expenses = []
        for expense in expenses:
            if expense.payment_status in ['unpaid', 'partial']:
                unpaid_expenses.append(expense.id)
        
        return cls.objects.filter(id__in=unpaid_expenses)
    
    @classmethod
    def get_overdue_payments(cls):
        """هزینه‌های سررسید گذشته"""
        from django.utils import timezone
        today = timezone.now().date()
        
        expenses = cls.objects.filter(
            due_date__lt=today,
            approval_status__in=['approved', 'auto_approved']
        )
        
        # فیلتر کردن بر اساس وضعیت پرداخت محاسبه شده
        overdue_expenses = []
        for expense in expenses:
            if expense.payment_status in ['unpaid', 'partial']:
                overdue_expenses.append(expense.id)
        
        return cls.objects.filter(id__in=overdue_expenses)
    
    @classmethod
    def get_monthly_total(cls, year, month):
        """مجموع هزینه‌های ماهانه"""
        return cls.objects.filter(
            expense_date__year=year,
            expense_date__month=month,
            approval_status__in=['approved', 'auto_approved']
        ).aggregate(
            total=models.Sum('final_amount')
        )['total'] or Decimal('0')
    
    @classmethod
    def get_cost_by_type(cls, cost_type, year=None, month=None):
        """هزینه‌ها بر اساس نوع"""
        queryset = cls.objects.filter(
            cost_type=cost_type,
            approval_status__in=['approved', 'auto_approved']
        )
        
        if year:
            queryset = queryset.filter(expense_date__year=year)
        if month:
            queryset = queryset.filter(expense_date__month=month)
            
        return queryset.aggregate(
            total=models.Sum('final_amount')
        )['total'] or Decimal('0')
    
    @classmethod
    def get_total_paid_amount(cls, year=None, month=None):
        """محاسبه کل مبلغ پرداخت شده (بر اساس تراکنش‌های تأیید شده)"""
        from fledger.models import Transaction
        
        queryset = Transaction.objects.filter(
            hazinah__isnull=False,
            transaction_type='Hazinah',
            status='approved',
            amount__lt=0  # هزینه‌ها منفی هستند
        )
        
        if year:
            queryset = queryset.filter(approved_at__year=year)
        if month:
            queryset = queryset.filter(approved_at__month=month)
        
        total = queryset.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
        
        return abs(total)  # برگرداندن مقدار مثبت
    
    @classmethod
    def get_pending_payment_amount(cls):
        """محاسبه کل مبلغ در انتظار پرداخت"""
        expenses = cls.objects.filter(
            approval_status__in=['approved', 'auto_approved']
        )
        
        total_pending = Decimal('0')
        for expense in expenses:
            if expense.payment_status in ['unpaid', 'partial']:
                total_pending += expense.remaining_amount
        
        return total_pending
