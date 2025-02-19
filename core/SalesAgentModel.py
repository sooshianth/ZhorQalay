from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

class SalesAgent(models.Model):
    user = models.OneToOneField('auth.User', on_delete=models.DO_NOTHING, related_name='sales_agent')
    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, unique=True)

    class Meta:
        verbose_name = 'کارشناس فروش'
        verbose_name_plural = 'کارشناسان فروش'

    # مشتریان این کارشناس
    def get_all_customers(self):
        return self.customers.all()
    

    # لیست فروش‌های این ماه
    def get_this_month_sales(self):
        from django.utils.timezone import now  # وارد کردن `now` برای گرفتن ماه فعلی
        this_month_sales = []
        
        for customer in self.get_all_customers():  # بررسی تمام مشتری‌ها
            this_month_sales.extend(customer.purchases_made.filter(
                is_archived=False, 
                is_paid=True, 
                created_at__month=now().month
            ))  # فیلتر کردن خریدهای این ماه برای هر مشتری

        return this_month_sales

    # مجموع مبلغ فروش‌های این ماه
    def get_this_month_sales_amount(self):
        return sum([purchase.amount_paid for purchase in self.get_this_month_sales()])
    # مجموع وزن فروش‌های این ماه
    def get_this_month_sales_weight(self):
        return sum([purchase.weight for purchase in self.get_this_month_sales()])
    # تعداد فروش‌های این ماه
    def get_this_month_sales_count(self):
        return len(self.get_this_month_sales())
    # میانگین مبلغ فروش‌های این ماه
    def get_this_month_sales_average(self):
        return self.get_this_month_sales_amount() / self.get_this_month_sales_count()
    

    # فروش‌های احتمالی (کوتاژ ارسال شده هنوز خرید انجام نشده)
    def get_potentional_sales(self):
        return self.customers.all().purchases_made.all().filter(is_archived=False, is_paid=False)
    
    # فروش‌های احتمالی و در جریان 
    def get_all_unpaid_sales(self):
        unpaid_sales = []
        customers = self.get_all_customers()  # اینجا تمام مشتری‌ها رو می‌گیریم
        for customer in customers:
            unpaid_sales.extend(customer.purchases_made.filter(is_paid=False))  # فیلتر خریدهای پرداخت نشده هر مشتری
        return unpaid_sales

    # همه فروش های آرشیو شده این کارشناس
    def get_all_active_sales(self):
        active_sales = []
        for customer in self.get_all_customers():  # بررسی تمام مشتری‌ها
            active_sales.extend(customer.purchases_made.filter(is_archived=False, is_paid=True))  # فیلتر خریدهای فعال
        return active_sales

    def get_all_archived_sales(self):
        archived_sales = []
        for customer in self.get_all_customers():  # بررسی تمام مشتری‌ها
            archived_sales.extend(customer.purchases_made.filter(is_archived=True, is_paid=True))  # فیلتر خریدهای آرشیو شده
        return archived_sales


    # پیگیری های انجام نشده
    def get_all_undone_tasks(self):
        return self.customers.all().tasks.all().filter(status=False)
    # کل پیگیری های روز
    def get_today_tasks(self):
        return self.customers.all().tasks.all().filter(due_date__date=timezone.now().date())
    def get_all_tasks(self):
        tasks = []
        for customer in self.get_all_customers():
            tasks.extend(customer.tasks.all())  # فیلتر کردن تسک‌ها برای هر مشتری
        return tasks


    def __str__(self):
        return self.name
    
    def clean(self):
        if SalesAgent.objects.filter(phone_number=self.phone_number).exists():
            raise ValidationError('شماره تلفن تکراری است.')
        if len(self.phone_number) < 11:
            raise ValidationError('شماره تلفن باید 11 رقم باشد.')
        if not self.phone_number.isdigit():
            raise ValidationError('شماره تلفن باید عدد باشد.')
        if not self.name:
            raise ValidationError('نام نمی‌تواند خالی باشد.')
        if len(self.name) < 3:
            raise ValidationError('نام باید حداقل 3 حرف باشد.')
        if len(self.name) > 100:
            raise ValidationError('نام نمی‌تواند بیشتر از 100 حرف باشد.')
        