from django.contrib import admin
from django.contrib.admin import actions
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.db.models import Q
from admin_list_charts.admin import ListChartMixin
from .CallSessionModel import CallSession
from .CargoProductModel import CargoProduct
from .CustomerModel import Customer, PhoneNumber, CrmAccessNumbers, FIELD_OF_ACTIVITY, ActivityField, ProductPreference, PaymentPreference
from .FinancialManagerModel import FinancialManager
from .LogisticsManagerModel import LogisticsManager
from .PurchaseModel import Purchase, PurchaseHistory, ShenaseTakhsis, PurchaseReceipts, PurchaseStateChange
from .SalesAgentModel import SalesAgent
from .TaskModel import Task
from .NotificationModel import Notification
from .SupportAgentModel import SupportAgent
from .SupportAgentTask import SupportAgentTask
from .AccountNumber import AccountNumber
from .LogViewerModel import LogViewer
from sms_api.models import SmsQueue
from sms_api.apis import queue_sms
from django.urls import path
from django.template.response import TemplateResponse
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib.admin.sites import site
from bki_barnameh.models.BarnamehModel import Barnameh
from .CargoProductModel import VaredKonandeh, Barbary, VaredKonandehTransaction
# @admin.register(Notification)
# class NotificationAdmin(admin.ModelAdmin):
#     list_display = ('user', 'message')

# تنظیمات نمایش مدل CargoProduct در ادمین
import logging
from core.logging_levels import *
logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def get_client_ip(request):
    """
    دریافت IP کامل کلاینت (محلی و خارجی، پشتیبانی از proxy و load balancer)
    """
    if not request:
        return "Unknown"
        
    # IP مستقیم (از سرور دیده می‌شود)
    direct_ip = request.META.get('REMOTE_ADDR', 'Unknown')
        
    # IP از طریق proxy headers
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    real_ip = request.META.get('HTTP_X_REAL_IP')

    # انتخاب IP اصلی
    client_ip = direct_ip
    if forwarded_for:
        # اولین IP در لیست X-Forwarded-For
        client_ip = forwarded_for.split(',')[0].strip()
    elif real_ip:
        client_ip = real_ip
        
    # اگر proxy وجود دارد، هر دو IP را نمایش بده
    if forwarded_for or real_ip:
        proxy_info = f" (via {direct_ip})"
    else:
        proxy_info = ""
        
    return f"{client_ip}-{proxy_info}"

from django.contrib.admin import AdminSite

class AttendanceAdminSite(AdminSite):
    site_header = "مدیریت حضور و حقوق"
    site_title = "پنل مدیریت حضور و حقوق"
    index_title = "خوش آمدید به بخش مدیریت حضور و حقوق"

# Custom admin action to login as user
def login_as_user(modeladmin, request, queryset):
    audit_logger.activity(f"user tried to login as admin as another user.")
    # Only allow one user at a time
    if request.user.is_superuser:    
        if queryset.count() != 1:
            modeladmin.message_user(request, "لطفا فقط یک کاربر را انتخاب کنید", level="error")
            return
        
        # Get the selected user
        target_user = queryset.first()
        
        # Save the original user ID in session to allow switching back
        request.session['admin_user_id'] = request.user.id
        
        # Login as the selected user
        login(request, target_user)
        
        # Redirect to home page
        return HttpResponseRedirect('/')
    else:
        audit_logger.alert(f"User {request.user.username} tried to login as {target_user.username}.")
        return HttpResponseRedirect('/')

login_as_user.short_description = "ورود به عنوان کاربر انتخاب شده"

# Register the User model with admin site
# ابتدا User را از admin خارج می‌کنیم
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass  # اگر قبلا ثبت نشده باشد، خطا را نادیده می‌گیریم

# سپس User را با تنظیمات خودمان ثبت می‌کنیم
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    actions = [login_as_user]

@admin.register(CargoProduct)
class CargoProductAdmin(ListChartMixin, admin.ModelAdmin):
    list_display = ('cottage', 'product_type', 'country', 'vared_konandeh', 'port', 'weight', 'status', 'barbary')
    list_filter = ('product_type', 'country', 'vared_konandeh', 'port', 'status', 'barbary')
    search_fields = ('cottage', 'vared_konandeh__name', 'barbary__name')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'

class PhoneNumberInline(admin.TabularInline):
    model = PhoneNumber
    extra = 1

class CrmAccessNumbersInline(admin.TabularInline):
    model = CrmAccessNumbers
    extra = 1
    fields = ('phone_number',)
    verbose_name = "شماره مجاز در CRM"
    verbose_name_plural = "شماره‌های مجاز در CRM"

class PurchaseInline(admin.TabularInline):
    model = Purchase
    fk_name = 'customer'  # مشخص کردن کدام ForeignKey استفاده شود
    fields = ( 'purchase_number', 'order_weight', 'delivered_weight', 'amount_paid', 'state', 'created_at')
    extra = 0

class CustomerProductFilter(admin.SimpleListFilter):
    title = 'محصول خریداری شده'
    parameter_name = 'product_type'

    def lookups(self, request, model_admin):
        return CargoProduct.PRODUCT_TYPES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(purchases_made__cargo__product_type=self.value()).distinct()
        return queryset

class CustomerCountryFilter(admin.SimpleListFilter):
    title = 'کشور مبدا محصول'
    parameter_name = 'country'

    def lookups(self, request, model_admin):
        return CargoProduct.COUNTRIES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(purchases_made__cargo__country=self.value()).distinct()
        return queryset

class CustomerProductCountryFilter(admin.SimpleListFilter):
    title = 'محصول و کشور'
    parameter_name = 'product_country'

    def lookups(self, request, model_admin):
        # ایجاد لیستی از ترکیب‌های نوع محصول و کشور که توسط مشتریان خریداری شده‌اند
        combinations = CargoProduct.objects.values('product_type', 'country').distinct()
        result = []
        for combo in combinations:
            product_type = dict(CargoProduct.PRODUCT_TYPES).get(combo['product_type'], '')
            country = dict(CargoProduct.COUNTRIES).get(combo['country'], '')
            value = f"{combo['product_type']}_{combo['country']}"
            label = f"{product_type} {country}"
            result.append((value, label))
        return sorted(result, key=lambda x: x[1])  # مرتب‌سازی بر اساس برچسب

    def queryset(self, request, queryset):
        if self.value():
            product_type, country = self.value().split('_')
            return queryset.filter(
                purchases_made__cargo__product_type=product_type,
                purchases_made__cargo__country=country
            ).distinct()
        return queryset

class CustomerPurchaseStatusFilter(admin.SimpleListFilter):
    title = 'وضعیت خرید'
    parameter_name = 'purchase_status'

    def lookups(self, request, model_admin):
        return Purchase.STATUS_CHOICES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(purchases_made__state=self.value()).distinct()
        return queryset

class CustomerPurchaseDateFilter(admin.SimpleListFilter):
    title = 'زمان خرید اخیر'
    parameter_name = 'purchase_date'

    def lookups(self, request, model_admin):
        return (
            ('week', 'در هفته گذشته'),
            ('month', 'در ماه گذشته'),
            ('quarter', 'در سه ماه گذشته'),
            ('year', 'در سال گذشته'),
        )

    def queryset(self, request, queryset):
        import datetime
        import jdatetime
        from django.utils import timezone
        
        if self.value() == 'week':
            start_date = timezone.now() - datetime.timedelta(days=7)
            return queryset.filter(purchases_made__created_at__gte=start_date).distinct()
        elif self.value() == 'month':
            start_date = timezone.now() - datetime.timedelta(days=30)
            return queryset.filter(purchases_made__created_at__gte=start_date).distinct()
        elif self.value() == 'quarter':
            start_date = timezone.now() - datetime.timedelta(days=90)
            return queryset.filter(purchases_made__created_at__gte=start_date).distinct()
        elif self.value() == 'year':
            start_date = timezone.now() - datetime.timedelta(days=365)
            return queryset.filter(purchases_made__created_at__gte=start_date).distinct()
        return queryset

class CustomerCargoFilter(admin.SimpleListFilter):
    title = 'کوتاژ محصول'
    parameter_name = 'cargo'

    def lookups(self, request, model_admin):
        # محصولات فعال که موجودی بیشتر از صفر دارند را نمایش می‌دهیم
        cargos = CargoProduct.objects.filter(status=True, weight__gt=0).order_by('-created_at')
        return [(cargo.id, f'{cargo.cottage} - {cargo.get_product_type_display()} {cargo.get_country_display()}') for cargo in cargos]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(purchases_made__cargo_id=self.value()).distinct()
        return queryset

class CustomerSpecificCargoFilter(admin.SimpleListFilter):
    title = 'کوتاژ خریداری شده'
    parameter_name = 'purchased_cargo'

    def lookups(self, request, model_admin):
        # کوتاژهایی که حداقل یک مشتری برای آنها خرید ثبت کرده است
        cargos_with_purchases = CargoProduct.objects.filter(purchases__isnull=False).distinct()
        return [(cargo.id, f'{cargo.cottage} - {cargo.get_product_type_display()} {cargo.get_country_display()}') for cargo in cargos_with_purchases]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(purchases_made__cargo_id=self.value()).distinct()
        return queryset

@admin.register(Customer)
class CustomerAdmin(ListChartMixin, admin.ModelAdmin):
    search_fields = ('name', 'phone_number', 'phone_numbers__number', 'city', 'purchases_made__purchase_number', 'purchases_made__cargo__cottage')
    list_display = ('pk', 'name', 'get_primary_phone', 'city', 'get_total_purchases', 'get_last_purchase_date')
    list_filter = ('field_of_activity', 'city', 'sms_preference', 'whatsapp_preference', 'day_of_week', 'is_bazaargah_enjoyer', CustomerProductFilter, CustomerCountryFilter, CustomerProductCountryFilter, CustomerPurchaseStatusFilter, CustomerPurchaseDateFilter, CustomerCargoFilter, CustomerSpecificCargoFilter)
    ordering = ('-created_at',)
    inlines = [PhoneNumberInline, CrmAccessNumbersInline, PurchaseInline]
    actions = ['send_custom_sms']
    date_hierarchy = 'created_at'
    
    def get_primary_phone(self, obj):
        return obj.get_primary_phone()
    get_primary_phone.short_description = 'شماره تلفن اصلی'
    
    def get_total_purchases(self, obj):
        return obj.purchases_made.count()
    get_total_purchases.short_description = 'تعداد خریدها'
    
    def get_last_purchase_date(self, obj):
        last_purchase = obj.purchases_made.order_by('-created_at').first()
        return last_purchase.created_at if last_purchase else '-'
    get_last_purchase_date.short_description = 'آخرین خرید'

    def send_custom_sms(self, request, queryset):
        audit_logger.info(f"user tried to send custom sms.")
        if 'apply' in request.POST:
            message = request.POST.get('message', '')
            notification_type = request.POST.get('notification_type', 'custom')
            suspended = 'suspended' in request.POST
            scheduled_time_str = request.POST.get('scheduled_time', '')
            sent_count = 0
            error_count = 0
            error_messages = []
            
            # تنظیم timezone و زمان پیش‌فرض
            from django.utils import timezone
            import datetime
            default_time = timezone.now()
            
            # تبدیل رشته زمان به شیء datetime
            scheduled_for = default_time  # استفاده از زمان فعلی به عنوان پیش‌فرض
            if scheduled_time_str:
                try:
                    # تبدیل فرمت 2023-05-20T15:30 به datetime
                    naive_datetime = datetime.datetime.strptime(scheduled_time_str, '%Y-%m-%dT%H:%M')
                    # تبدیل به timezone-aware datetime
                    scheduled_for = timezone.make_aware(naive_datetime)
                    logger.debug(f"Scheduled for: {scheduled_for}")
                except Exception as e:
                    scheduled_for = default_time  # استفاده از زمان فعلی در صورت خطا
                    logger.error(f"Error parsing scheduled time: {e}, schedule for: {scheduled_for}")
            
            if not message:
                self.message_user(request, 'لطفاً متن پیامک را وارد کنید.', level='error')
                return HttpResponseRedirect(request.get_full_path())
            
            # برای اطمینان از عملکرد فرم
            logger.debug(f"Form submitted - message: {message}, notification_type: {notification_type}, suspended: {suspended}")
            logger.debug(f"Scheduled for: {scheduled_for}")
            logger.debug(f"Selected customers count: {queryset.count()}")
            
            # آمار قبل از ایجاد
            before_stats = DebugSmsQueue.print_sms_queue_stats()
            
            for customer in queryset:
                # دریافت تمام شماره‌های تلفن مشتری
                phone_numbers = customer.get_all_phone_numbers()
                # اطمینان از وجود حداقل یک شماره تلفن
                if not phone_numbers:
                    error_message = f"Customer {customer.name}: no phone numbers found"
                    logger.warning(error_message)
                    error_messages.append(error_message)
                    error_count += 1
                    continue
                
                # ارسال پیامک به تمام شماره‌های تلفن
                customer_success = 0
                
                for phone in phone_numbers:
                    try:
                        # استاندارد کردن شماره تلفن
                        if phone.startswith('+98'):
                            phone = '0' + phone[3:]
                        elif not phone.startswith('0'):
                            phone = '0' + phone

                        # تبدیل به فرمت 09xx
                        if not phone.startswith('09'):
                            if phone.startswith('9') and len(phone) == 10:
                                phone = '0' + phone  # تبدیل 9123456789 به 09123456789
                            else:
                                # اگر فرمت شماره درست نیست، به شماره بعدی برو
                                error_message = f"The phone number {phone} for customer {customer.name} is invalid. It must start with 09."
                                logger.warning(error_message)
                                continue
                        
                        # ایجاد مستقیم رکورد در دیتابیس با اطمینان از فرمت صحیح
                        status = 'suspended' if suspended else 'pending'
                        
                        if len(phone) != 11 or not phone.startswith('09'):
                            raise ValueError(f"شماره تلفن {phone} نامعتبر است. باید 11 رقمی و با 09 شروع شود.")
                        
                        # ایجاد پیامک با زمان ارسال مشخص شده
                        sms_queue = SmsQueue.objects.create(
                            recipient_number=phone,
                            message=message,
                            notification_type=notification_type,
                            status=status,
                            is_suspended=suspended,
                            scheduled_for=scheduled_for  # همیشه یک مقدار معتبر خواهد داشت
                        )
                        
                        if sms_queue and sms_queue.id:
                            customer_success += 1
                            sent_count += 1
                        else:
                            raise ValueError("خطای ناشناخته در ایجاد پیامک")
                            
                    except Exception as e:
                        error_message = f"مشتری {customer.name} - شماره {phone}: {str(e)}"
                        error_messages.append(error_message)
                        error_count += 1
                
                # اگر برای هیچکدام از شماره‌های این مشتری پیامک ارسال نشده
                if customer_success == 0:
                    error_message = f"مشتری {customer.name}: ارسال پیامک به هیچ شماره‌ای موفق نبود"
                    if error_message not in error_messages:
                        error_messages.append(error_message)
            
            # آمار بعد از ایجاد
            after_stats = DebugSmsQueue.print_sms_queue_stats()
            
            # نمایش نتیجه به کاربر
            if sent_count > 0:
                success_msg = f'پیامک برای {sent_count} شماره تلفن در صف ارسال قرار گرفت.'
                if scheduled_for:
                    success_msg += f' زمان ارسال: {scheduled_for.strftime("%Y-%m-%d %H:%M")}'
                self.message_user(request, success_msg)
            
            if error_count > 0:
                error_msg = f'{error_count} errors occurred while sending SMS: {", ".join(error_messages[:5])}'
                if len(error_messages) > 5:
                    error_msg += "..."
                logger.warning(error_msg)
                self.message_user(request, error_msg, level='error')
            
            logger.info("بازگشت به صفحه اصلی...")
            return HttpResponseRedirect(request.get_full_path())
            
        return render(request, 'admin/send_custom_sms.html', {
            'customers': queryset,
            'notification_types': SmsQueue.NOTIFICATION_TYPES,
            'title': 'ارسال پیامک سفارشی'
        })
    send_custom_sms.short_description = 'ارسال پیامک سفارشی'
    
    def get_queryset(self, request):
        """
        بهینه‌سازی کوئری با اضافه کردن prefetch_related برای بهبود عملکرد
        """
        return super().get_queryset(request).prefetch_related(
            'phone_numbers', 
            'purchases_made', 
            'purchases_made__cargo',
            'sales_agent'
        )

class ShenaseTakhsisInline(admin.TabularInline):
    model = ShenaseTakhsis
    extra = 1
    verbose_name = "شناسه تخصیص"
    verbose_name_plural = "شناسه‌های تخصیص"

class PurchaseReceiptsInline(admin.TabularInline):
    model = PurchaseReceipts
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('reciept_type', 'reciept_file', 'user', 'created_at')
    verbose_name = "رسید خرید"
    verbose_name_plural = "رسیدهای خرید"

# تنظیمات نمایش مدل Purchase در ادمین
@admin.register(Purchase)
class PurchaseAdmin(ListChartMixin, admin.ModelAdmin):
    list_display = ('invoice_id', 'purchase_number', 'customer', 'order_weight', 'delivered_weight', 'amount_paid', 'created_at')
    list_filter = ('customer', 'type', 'state', 'cargo__product_type', 'cargo__country')
    search_fields = ('invoice_id', 'purchase_number', 'customer__name', 'customer__phone_number', 'customer__sales_agent__name')
    ordering = ('-created_at',)
    inlines = [ShenaseTakhsisInline, PurchaseReceiptsInline]
    date_hierarchy = 'created_at'

# تنظیمات نمایش مدل PurchaseHistory در ادمین
# @admin.register(PurchaseHistory)
# class PurchaseHistoryAdmin(admin.ModelAdmin):
#     list_display = ('purchase', 'user', 'timestamp')
#     list_filter = ('timestamp',)
#     search_fields = ('purchase__purchase_number', 'user__username')
#     ordering = ('-timestamp',)

@admin.register(ShenaseTakhsis)
class ShenaseTakhsisAdmin(ListChartMixin, admin.ModelAdmin):
    list_display = ('purchase', 'code', 'weight','created_at')
    list_filter = ('created_at',)
    search_fields = ('purchase__purchase_number', 'code')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'


# تنظیمات نمایش مدل Task در ادمین
# @admin.register(Task)
# class TaskAdmin(admin.ModelAdmin):
#     list_display = ('customer', 'description', 'status', 'due_date',  'create_time')
#     list_filter = ('status',)
#     search_fields = ('customer__name', 'description')
#     ordering = ('due_date',)

# تنظیمات نمایش مدل CallSession در ادمین
@admin.register(CallSession)
class CallSessionAdmin(ListChartMixin, admin.ModelAdmin):
    list_display = ('customer', 'date')
    list_filter = ('date', 'customer__sales_agent')
    ordering = ('-date',)
    date_hierarchy = 'date'


# تنظیمات نمایش مدل SalesAgent در ادمین
@admin.register(SalesAgent)
class SalesAgentAdmin(ListChartMixin, admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'user')
    search_fields = ('name', 'phone_number')
    ordering = ('name',)
    date_hierarchy = 'user__date_joined'


# تنظیمات نمایش مدل FinancialManager در ادمین
@admin.register(FinancialManager)
class FinancialManagerAdmin(ListChartMixin, admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'user')
    search_fields = ('name', 'phone_number')
    ordering = ('name',)
    date_hierarchy = 'user__date_joined'

# تنظیمات نمایش مدل LogisticsManager در ادمین
@admin.register(LogisticsManager)
class LogisticsManagerAdmin(ListChartMixin, admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'user')
    search_fields = ('name', 'phone_number')
    ordering = ('name',)
    date_hierarchy = 'user__date_joined'

# @admin.register(PhoneNumber)
# class PhoneNumberAdmin(admin.ModelAdmin):
#     list_display = ('number', 'customer', 'is_primary')
#     list_filter = ('is_primary',)
#     search_fields = ('number', 'customer__name')
#     raw_id_fields = ('customer',)

@admin.register(SupportAgent)
class SupportAgentAdmin(ListChartMixin, admin.ModelAdmin):
    list_display = ('name', 'email', 'phone_number', 'message', 'created_at', 'updated_at')
    search_fields = ('name', 'email', 'phone_number', 'message')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'


# @admin.register(PurchaseStateChange)
# class PurchaseStateChangeAdmin(admin.ModelAdmin):
#     list_display = ('purchase', 'previous_state', 'new_state', 'changed_by', 'changed_at')
#     list_filter = ('previous_state', 'new_state')
#     search_fields = ('purchase__purchase_number', 'changed_by__username')
#     ordering = ('-changed_at',)

# اضافه کردن نمایش دیباگ برای پیامک‌ها به جای ثبت مجدد SmsQueue
class DebugSmsQueue:
    @staticmethod
    def print_sms_queue_stats():
        from sms_api.models import SmsQueue
        pending = SmsQueue.objects.filter(status='pending').count()
        sent = SmsQueue.objects.filter(status='sent').count()
        failed = SmsQueue.objects.filter(status='failed').count()
        suspended = SmsQueue.objects.filter(status='suspended').count()
        total = SmsQueue.objects.count()
        
        logger.debug("SMS queue stats:")
        logger.debug(f"Total: {total}, Pending: {pending}, Sent: {sent}, Failed: {failed}, Suspended: {suspended}")
        return pending, sent, failed, suspended, total

# @admin.register(ActivityField)
# class ActivityFieldAdmin(admin.ModelAdmin):
#     list_display = ('code', '__str__')
#     search_fields = ('code',)

# @admin.register(ProductPreference)
# class ProductPreferenceAdmin(admin.ModelAdmin):
#     list_display = ('code', '__str__')
#     search_fields = ('code',)

# @admin.register(PaymentPreference)
# class PaymentPreferenceAdmin(admin.ModelAdmin):
#     list_display = ('code', '__str__')
#     search_fields = ('code',)

# admin.site.unregister(User)

@admin.register(Barnameh)
class BarnamehAdmin(ListChartMixin, admin.ModelAdmin):
    list_display = ('number', 'purchase_number', 'shenase_takhsis_code', 'serial', 'barnameh_date', 'is_sent_to_bki', 'is_sent_to_bki_at')
    list_filter = ('is_sent_to_bki', 'purchase__customer')
    search_fields = ('number', 'purchase_number', 'shenase_takhsis_code', 'serial')
    ordering = ('-barnameh_date',)
    date_hierarchy = 'barnameh_date'


from bki_barnameh.models.BarnamehModel import BarnamehLog
@admin.register(BarnamehLog)
class BarnamehLogAdmin(ListChartMixin, admin.ModelAdmin):
    list_display = ('barnameh', 'log_date', 'log_message')
    ordering = ('-log_date',)
    date_hierarchy = 'log_date'

@admin.register(VaredKonandeh)
class VaredKonandehAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'email', 'balance')
    search_fields = ('name', 'phone_number', 'email')

@admin.register(Barbary)
class BarbaryAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'email')
    search_fields = ('name', 'phone_number', 'email')

@admin.register(VaredKonandehTransaction)
class VaredKonandehTransactionAdmin(ListChartMixin, admin.ModelAdmin):
    list_display = ('vared_konandeh', 'amount', 'type', 'created_at')
    list_filter = ('type',)
    search_fields = ('vared_konandeh__name', 'amount', 'type')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'

@admin.register(SupportAgentTask)
class SupportAgentTaskAdmin(ListChartMixin, admin.ModelAdmin):
    list_display = ('support_agent', 'description', 'is_done', 'is_on_admin', 'created_at', 'due_date')
    list_filter = ('is_done', 'is_on_admin', 'urgency_level')
    search_fields = ('support_agent__name', 'description')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'

from core.SalesAgentModel import PhoneAssignment
@admin.register(PhoneAssignment)
class PhoneAssignmentAdmin(ListChartMixin, admin.ModelAdmin):
    list_display = ('phone_number', 'sales_agent', 'status', 'customer_name', 'sub_branch', 'sub_branch_phone', 'city', 'user_type', 'created_at',)
    list_filter = ('status', 'sales_agent')
    search_fields = ('phone_number', 'sales_agent__name')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'


@admin.register(AccountNumber)
class AccountNumberAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'customer', 'bank_name', 'account_number',
        'account_holder_name', 'is_active', 'created_at'
    )
    list_filter = ('bank_name', 'is_active', 'created_at')
    search_fields = (
        'customer__name', 'customer__phone_number',
        'bank_name', 'account_number', 'account_holder_name'
    )
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 25
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('اطلاعات مشتری', {
            'fields': ('customer',)
        }),
        ('اطلاعات حساب بانکی', {
            'fields': (
                'bank_name', 'account_number', 'account_holder_name'
            )
        }),
        ('وضعیت', {
            'fields': ('is_active',)
        }),
        ('توضیحات', {
            'fields': ('description',),
            'classes': ('collapse',)
        }),
        ('تاریخ‌ها', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('customer')


from core.logging_filters import CircularBufferHandler

@admin.register(LogViewer)
class LogViewerAdmin(admin.ModelAdmin):
    """
    پنل ادمین برای نمایش لاگ‌های ذخیره شده در حافظه
    """
    
    class Media:
        css = {
            'all': ('admin/css/log_viewer.css',)
        }
    
    def has_add_permission(self, request):
        # غیرفعال کردن دکمه افزودن
        return False
    
    def has_delete_permission(self, request, obj=None):
        # غیرفعال کردن دکمه حذف
        return False
    
    def has_change_permission(self, request, obj=None):
        # غیرفعال کردن دکمه ویرایش
        return False
    
    def changelist_view(self, request, extra_context=None):
        """
        نمایش سفارشی برای لیست لاگ‌ها
        """
        # دریافت handler
        handler = CircularBufferHandler()
        
        # دریافت پارامترهای فیلتر از URL
        level_filter = request.GET.get('level', '')
        logger_filter = request.GET.get('logger', '')
        limit = request.GET.get('limit', '100')
        
        # تبدیل limit به عدد صحیح
        try:
            limit = int(limit) if limit else 100
        except ValueError:
            limit = 100
        
        # دریافت لاگ‌ها
        logs = handler.get_logs(
            level=level_filter if level_filter else None,
            logger_name=logger_filter if logger_filter else None,
            limit=limit
        )
        
        # دریافت آمار
        stats = handler.get_stats()
        
        # دریافت لیست logger های منحصر به فرد
        unique_loggers = sorted(stats.get('loggers', {}).keys())
        
        # اگر درخواست پاک کردن لاگ‌ها بود
        if request.GET.get('action') == 'clear' and request.user.is_superuser:
            handler.clear()
            audit_logger.activity(f"Logs cleared by {request.user.username}.")
            return HttpResponseRedirect(request.path)
        
        # ایجاد context برای template
        context = {
            'title': 'نمایشگر لاگ‌های حافظه',
            'logs': logs,
            'stats': stats,
            'unique_loggers': unique_loggers,
            'level_filter': level_filter,
            'logger_filter': logger_filter,
            'limit': limit,
            'has_clear_permission': request.user.is_superuser,
        }
        
        if extra_context:
            context.update(extra_context)
        
        return TemplateResponse(request, 'admin/log_viewer.html', context)


