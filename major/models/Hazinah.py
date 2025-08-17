from django.db import models
from django_jalali.db import models as jmodels
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from decimal import Decimal

class Hazinah(models.Model):
    """
    مدل هزینه برای کنترل تمام هزینه‌های شرکت
    """
    
    COST_TYPES = [
        ('product_purchase', 'خرید محصول'),
        ('customer_allocation', 'تخصیص مشتری در کارخانه'),
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
        ('auto_approved', 'تأیید خودکار'),
        ('pending_admin', 'در انتظار تأیید ادمین'),
        ('financial_approved', 'تأیید مدیر مالی')
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
    amount = models.DecimalField(_('مبلغ (ریال)'), max_digits=15, decimal_places=0, null=True, blank=True)
    
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
        
        # اگر نوع هزینه "خرید محصول" یا "تخصیص مشتری" است، مبلغ اختیاری است (از فاکتور محاسبه می‌شود)
        # برای سایر انواع هزینه، مبلغ الزامی است
        if self.cost_type not in ['product_purchase', 'customer_allocation'] and not self.amount:
            raise ValidationError({
                'amount': _('برای این نوع هزینه، وارد کردن مبلغ الزامی است.')
            })
        
        if self.cost_type == 'other' and not self.description:
            raise ValidationError({
                'description': _('برای هزینه‌های "سایر"، توضیحات الزامی است.')
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

    
    def save(self, *args, **kwargs):
        """ذخیره با محاسبه مبلغ نهایی و بررسی تأیید خودکار"""
        from django.utils import timezone
        
        # اگر نوع هزینه "خرید محصول" یا "تخصیص مشتری" است و فاکتور دارد، مبلغ را از فاکتورها محاسبه کن
        # فقط در صورتی که از طریق update_from_invoices فراخوانی نشده باشد
        if (self.pk and self.cost_type in ['product_purchase', 'customer_allocation'] and self.has_invoices and 
            not getattr(self, '_updating_from_invoices', False)):
            self.amount = self.calculate_amount_from_invoices()
        
        # اگر مبلغ تنظیم نشده (برای هزینه‌های خرید محصول بدون فاکتور)، آن را صفر قرار بده
        if not self.amount:
            self.amount = 0
        
        # محاسبه مبلغ نهایی
        self.final_amount = self.amount + self.tax_amount - self.discount_amount

        # بررسی تأیید خودکار برای هزینه‌های جدید
        if not self.pk and self.approval_status == 'pending':
            self.approval_status = self._get_auto_approval_status()
            if self.approval_status == 'auto_approved':
                self.approval_date = timezone.now()
                self.approval_notes = 'تأیید خودکار - مبلغ کمتر از 10 میلیون تومان'
        
        super().save(*args, **kwargs)
    
    def update_amount_from_invoices(self):
        """بروزرسانی مبلغ هزینه از فاکتورها و بررسی مجدد وضعیت تأیید"""
        from django.utils import timezone
        
        # فقط برای هزینه‌های خرید محصول و تخصیص مشتری
        if self.cost_type in ['product_purchase', 'customer_allocation'] and self.has_invoices:
            self._updating_from_invoices = True
            old_amount = self.amount
            self.amount = self.calculate_amount_from_invoices()
            
            # محاسبه مبلغ نهایی جدید
            new_final_amount = self.amount + self.tax_amount - self.discount_amount
            
            # بررسی مجدد وضعیت تأیید اگر مبلغ تغییر کرده باشد
            if old_amount != self.amount and self.approval_status in ['auto_approved', 'pending']:
                new_approval_status = self._get_auto_approval_status()
                
                # اگر وضعیت تأیید تغییر کرده باشد
                if new_approval_status != self.approval_status:
                    self.approval_status = new_approval_status
                    
                    if new_approval_status == 'auto_approved':
                        self.approval_date = timezone.now()
                        self.approval_notes = 'تأیید خودکار - مبلغ کمتر از 10 میلیون تومان'
                    elif new_approval_status == 'pending':
                        # اگر از auto_approved به pending تغییر کرده، تاریخ تأیید را پاک کن
                        self.approval_date = None
                        self.approval_notes = ''
            
            self.save()
            delattr(self, '_updating_from_invoices')
    
    def __str__(self):
        return f"{self.get_cost_type_display()} - {self.title} - {self.amount:,} ریال"
    
    @property
    def payment_status(self):
        """محاسبه وضعیت پرداخت بر اساس تراکنش‌ها"""
        transactions = self.transactions.filter(status='approved')
        
        if not transactions.exists():
            return 'unpaid'
        
        # برای هزینه‌ها، تراکنش‌های پرداخت مثبت ذخیره می‌شوند
        total_paid = sum(transaction.amount for transaction in transactions if transaction.amount > 0)
        # اگر تراکنش منفی باشد (مثل برگشت) از کل کم می‌شود
        total_refunded = sum(abs(transaction.amount) for transaction in transactions if transaction.amount < 0)
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
        # برای هزینه‌ها، تراکنش‌های پرداخت مثبت ذخیره می‌شوند
        total_paid = sum(transaction.amount for transaction in transactions if transaction.amount > 0)
        # اگر تراکنش منفی باشد (مثل برگشت) از کل کم می‌شود
        total_refunded = sum(abs(transaction.amount) for transaction in transactions if transaction.amount < 0)
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
            'auto_approved': 'info',
            'pending_admin': 'warning',
            'financial_approved': 'info'
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
        return self.approval_status in ['pending', 'financial_approved']
    
    def can_be_paid(self):
        """آیا این هزینه قابل پرداخت است؟"""
        return (self.approval_status in ['approved', 'auto_approved'] and 
                self.payment_status in ['unpaid', 'partial'])

    def _get_auto_approval_status(self):
        """تعیین وضعیت تأیید بر اساس مبلغ"""
        # تبدیل ریال به تومان (تقسیم بر 10)
        amount_toman = self.final_amount / 10
        
        # اگر مبلغ صفر یا منفی است، همیشه نیاز به تأیید دستی دارد
        if amount_toman <= 0:
            return 'pending'
        elif amount_toman <= 10000000:  # 10 میلیون تومان
            return 'auto_approved'
        elif amount_toman <= 20000000:  # 20 میلیون تومان
            return 'pending'  # نیاز به تأیید مدیر مالی
        else:
            return 'pending'  # نیاز به تأیید مدیر مالی و سپس ادمین

    def get_required_approval_level(self):
        """تعیین سطح تأیید مورد نیاز"""
        amount_toman = self.final_amount / 10
        
        if amount_toman <= 0:
            return 'financial_manager'  # هزینه‌های صفر نیاز به تأیید مدیر مالی دارند
        elif amount_toman <= 10000000:
            return 'auto'
        elif amount_toman <= 20000000:
            return 'financial_manager'
        else:
            return 'admin'  # نیاز به تأیید مدیر مالی و سپس ادمین

    def can_be_approved_by(self, user):
        """بررسی اینکه آیا کاربر می‌تواند این هزینه را تأیید کند"""
        from core.decorators.det_user_role import determine_user_role
        
        if not user.is_authenticated:
            return False
            
        required_level = self.get_required_approval_level()
        user_role = determine_user_role(user)
        
        if required_level == 'auto':
            return False  # تأیید خودکار
        elif required_level == 'financial_manager':
            return user_role in ['admin', 'financial_manager']
        else:  # admin required (بالای 20 میلیون)
            if self.approval_status == 'pending':
                # فقط مدیر مالی می‌تواند تأیید اولیه کند
                return user_role == 'financial_manager'
            elif self.approval_status == 'financial_approved':
                # فقط ادمین می‌تواند تأیید نهایی کند
                return user_role == 'admin'
            
        return False

    def get_approval_info(self):
        """اطلاعات وضعیت تأیید"""
        amount_toman = self.final_amount / 10
        required_level = self.get_required_approval_level()
        
        info = {
            'amount_toman': amount_toman,
            'required_level': required_level,
            'current_status': self.approval_status,
        }
        
        if required_level == 'auto':
            info['message'] = 'تأیید خودکار (کمتر از 10 میلیون تومان)'
        elif required_level == 'financial_manager':
            info['message'] = 'نیاز به تأیید مدیر مالی (10-20 میلیون تومان)'
        else:
            info['message'] = 'نیاز به تأیید مدیر مالی و ادمین (بیش از 20 میلیون تومان)'
            
        return info
    
    def approve(self, approved_by_user, notes=None):
        """تأیید هزینه با در نظر گیری سطح دسترسی"""
        from django.utils import timezone
        from django.core.exceptions import ValidationError
        from core.decorators.det_user_role import determine_user_role
        
        if not self.can_be_approved_by(approved_by_user):
            raise ValidationError('شما مجاز به تأیید این هزینه نیستید.')
        
        required_level = self.get_required_approval_level()
        user_role = determine_user_role(approved_by_user)
        
        if required_level == 'admin' and user_role == 'financial_manager':
            # مدیر مالی در حال تأیید هزینه‌ای که نیاز به تأیید ادمین دارد
            self.approval_status = 'financial_approved'
            self.approved_by = approved_by_user
            self.approval_date = timezone.now()
            if notes:
                self.approval_notes = f"تأیید مدیر مالی: {notes}"
        else:
            # تأیید نهایی
            self.approval_status = 'approved'
            self.approved_by = approved_by_user
            self.approval_date = timezone.now()
            if notes:
                if self.approval_notes:
                    self.approval_notes += f"\n\nتأیید نهایی: {notes}"
                else:
                    self.approval_notes = notes
        
        self.save()
        return True
    
    def reject(self, rejected_by_user, notes=None):
        """رد هزینه"""
        from django.utils import timezone
        from django.core.exceptions import ValidationError
        
        valid_statuses = ['pending', 'financial_approved']
        if self.approval_status not in valid_statuses:
            raise ValidationError('فقط هزینه‌های در انتظار تأیید قابل رد هستند.')
        
        self.approval_status = 'rejected'
        self.approved_by = rejected_by_user
        self.approval_date = timezone.now()
        if notes:
            self.approval_notes = notes
        self.save()
        return True
    
    def create_payment_transaction(self, amount, wallet, payment_method=None, payment_reference=None, created_by=None, description=None):
        """ایجاد تراکنش پرداخت برای این هزینه"""
        from fledger.models import Transaction
        
        if not self.can_be_paid():
            return None, "این هزینه قابل پرداخت نیست"
        
        if amount <= 0:
            return None, "مبلغ باید بیشتر از صفر باشد"
        
        if amount > self.remaining_amount:
            return None, "مبلغ نمی‌تواند بیشتر از مبلغ باقی‌مانده باشد"
        
        # ایجاد تراکنش اصلی
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
        
        # اگر نوع هزینه "تخصیص مشتری" است، تراکنش به کیف پول مشتری نیز اضافه شود
        if self.cost_type == 'customer_allocation':
            # از فاکتورهای این هزینه، مشتری را پیدا کن
            invoice = self.invoices.first()
            if invoice and invoice.customer:
                # کیف پول مشتری را پیدا یا ایجاد کن
                customer_wallet, created = wallet.__class__.objects.get_or_create(
                    customer=invoice.customer,
                    defaults={'description': f'کیف پول {invoice.customer.name}'}
                )
                
                # تراکنش مثبت برای مشتری
                Transaction.objects.create(
                    wallet=customer_wallet,
                    transaction_type='Income',
                    amount=amount,  # مثبت چون درآمد برای مشتری است
                    hazinah=self,
                    payment_method=payment_method,
                    description=f"تخصیص از هزینه: {self.title}",
                    created_by=created_by,
                    status='pending'
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
    
    # متدهای مربوط به فاکتورها
    def calculate_amount_from_invoices(self):
        """محاسبه مبلغ کل از روی فاکتورهای مرتبط"""
        total = Decimal('0')
        for invoice in self.invoices.all():
            total += invoice.get_total_amount()
        return total
    
    @property
    def has_invoices(self):
        """آیا این هزینه فاکتور دارد؟"""
        return self.invoices.exists()
    
    @property
    def invoices(self):
        """فاکتورهای مرتبط با این هزینه"""
        return self.invoice_set.all()
    
    @property
    def total_invoice_amount(self):
        """کل مبلغ فاکتورهای مرتبط"""
        return self.calculate_amount_from_invoices()
    
    def get_invoice_summary(self):
        """خلاصه‌ای از فاکتورهای مرتبط"""
        invoices = self.invoices.all()
        total_amount = Decimal('0')
        total_items = 0
        
        for invoice in invoices:
            total_amount += invoice.get_total_amount()
            total_items += invoice.get_items_count()
        
        return {
            'count': invoices.count(),
            'total_amount': total_amount,
            'total_items': total_items,
            'invoices': invoices
        }
