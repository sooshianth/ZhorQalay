from django.contrib import admin
from django.contrib.admin import actions
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.db.models import Q
from .CallSessionModel import CallSession
from .CargoProductModel import CargoProduct
from .CustomerModel import Customer, PhoneNumber, FIELD_OF_ACTIVITY, ActivityField, ProductPreference, PaymentPreference
from .FinancialManagerModel import FinancialManager
from .LogisticsManagerModel import LogisticsManager
from .PurchaseModel import Purchase, PurchaseHistory, ShenaseTakhsis, PurchaseReceipts, PurchaseStateChange
from .SalesAgentModel import SalesAgent
from .TaskModel import Task
from .NotificationModel import Notification
from .SupportAgentModel import SupportAgent
from sms_api.models import SmsQueue
from sms_api.apis import queue_sms
from django.urls import path
from django.template.response import TemplateResponse
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib.admin.sites import site
from bki_barnameh.models.BarnamehModel import Barnameh
from .VaredKonandehModel import VaredKonandeh
from .BarbaryModel import Barbary
# @admin.register(Notification)
# class NotificationAdmin(admin.ModelAdmin):
#     list_display = ('user', 'message')

# تنظیمات نمایش مدل CargoProduct در ادمین


from django.contrib.admin import AdminSite

class AttendanceAdminSite(AdminSite):
    site_header = "مدیریت حضور و حقوق"
    site_title = "پنل مدیریت حضور و حقوق"
    index_title = "خوش آمدید به بخش مدیریت حضور و حقوق"

# Custom admin action to login as user
def login_as_user(modeladmin, request, queryset):
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
class CargoProductAdmin(admin.ModelAdmin):
    list_display = ('cottage', 'product_type', 'country', 'vared_konandeh', 'port', 'weight', 'status', 'barbary')
    list_filter = ('product_type', 'country', 'vared_konandeh', 'port', 'status', 'barbary')
    search_fields = ('cottage', 'vared_konandeh__name', 'barbary__name')
    ordering = ('-created_at',)

class PhoneNumberInline(admin.TabularInline):
    model = PhoneNumber
    extra = 1

class PurchaseInline(admin.TabularInline):
    model = Purchase
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
class CustomerAdmin(admin.ModelAdmin):
    search_fields = ('name', 'phone_number', 'phone_numbers__number', 'city', 'purchases_made__purchase_number', 'purchases_made__cargo__cottage')
    list_display = ('pk', 'name', 'get_primary_phone', 'city', 'get_total_purchases', 'get_last_purchase_date')
    list_filter = ('field_of_activity', 'city', 'sms_preference', 'whatsapp_preference', 'day_of_week', 'is_bazaargah_enjoyer', CustomerProductFilter, CustomerCountryFilter, CustomerProductCountryFilter, CustomerPurchaseStatusFilter, CustomerPurchaseDateFilter, CustomerCargoFilter, CustomerSpecificCargoFilter)
    ordering = ('-created_at',)
    inlines = [PhoneNumberInline, PurchaseInline]
    actions = ['send_custom_sms']
    
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
                    print(f"زمان ارسال: {scheduled_for}")
                except Exception as e:
                    print(f"خطا در تبدیل زمان: {e}")
                    scheduled_for = default_time  # استفاده از زمان فعلی در صورت خطا
            
            if not message:
                self.message_user(request, 'لطفاً متن پیامک را وارد کنید.', level='error')
                return HttpResponseRedirect(request.get_full_path())
            
            # برای اطمینان از عملکرد فرم
            print(f"فرم دریافت شد - پیام: {message}, نوع: {notification_type}, معلق: {suspended}")
            print(f"زمان ارسال: {scheduled_for}")
            print(f"تعداد مشتریان انتخاب شده: {queryset.count()}")
            
            # آمار قبل از ایجاد
            before_stats = DebugSmsQueue.print_sms_queue_stats()
            
            for customer in queryset:
                # دریافت تمام شماره‌های تلفن مشتری
                phone_numbers = customer.get_all_phone_numbers()
                print(f"مشتری: {customer.name}, تعداد شماره‌ها: {len(phone_numbers)}")
                
                # اطمینان از وجود حداقل یک شماره تلفن
                if not phone_numbers:
                    error_message = f"مشتری {customer.name}: هیچ شماره تلفنی یافت نشد"
                    print(error_message)
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
                                error_message = f"شماره تلفن {phone} برای مشتری {customer.name} نامعتبر است. باید با 09 شروع شود."
                                print(error_message)
                                continue
                        
                        # ایجاد مستقیم رکورد در دیتابیس با اطمینان از فرمت صحیح
                        status = 'suspended' if suspended else 'pending'
                        print(f"ایجاد پیامک با شماره: {phone}, وضعیت: {status}")
                        
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
                            print(f"پیامک ایجاد شد با شناسه: {sms_queue.id}")
                            customer_success += 1
                            sent_count += 1
                        else:
                            raise ValueError("خطای ناشناخته در ایجاد پیامک")
                            
                    except Exception as e:
                        error_message = f"مشتری {customer.name} - شماره {phone}: {str(e)}"
                        print(f"خطا: {error_message}")
                        error_messages.append(error_message)
                        error_count += 1
                
                # اگر برای هیچکدام از شماره‌های این مشتری پیامک ارسال نشده
                if customer_success == 0:
                    error_message = f"مشتری {customer.name}: ارسال پیامک به هیچ شماره‌ای موفق نبود"
                    if error_message not in error_messages:
                        error_messages.append(error_message)
            
            # آمار بعد از ایجاد
            after_stats = DebugSmsQueue.print_sms_queue_stats()
            print(f"تعداد پیامک‌های اضافه شده: {after_stats[4] - before_stats[4]}")
            
            # نمایش نتیجه به کاربر
            if sent_count > 0:
                success_msg = f'پیامک برای {sent_count} شماره تلفن در صف ارسال قرار گرفت.'
                if scheduled_for:
                    success_msg += f' زمان ارسال: {scheduled_for.strftime("%Y-%m-%d %H:%M")}'
                print(success_msg)
                self.message_user(request, success_msg)
            
            if error_count > 0:
                error_msg = f'{error_count} خطا در ارسال پیامک رخ داد: {", ".join(error_messages[:5])}'
                if len(error_messages) > 5:
                    error_msg += "..."
                print(error_msg)
                self.message_user(request, error_msg, level='error')
            
            print("بازگشت به صفحه اصلی...")
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
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('invoice_id', 'purchase_number', 'customer', 'order_weight', 'delivered_weight', 'amount_paid', 'created_at')
    list_filter = ('customer', 'type', 'state', 'cargo__product_type', 'cargo__country')
    search_fields = ('invoice_id', 'purchase_number', 'customer__name', 'customer__phone_number', 'customer__sales_agent__name')
    ordering = ('-created_at',)
    inlines = [ShenaseTakhsisInline, PurchaseReceiptsInline]

# تنظیمات نمایش مدل PurchaseHistory در ادمین
# @admin.register(PurchaseHistory)
# class PurchaseHistoryAdmin(admin.ModelAdmin):
#     list_display = ('purchase', 'user', 'timestamp')
#     list_filter = ('timestamp',)
#     search_fields = ('purchase__purchase_number', 'user__username')
#     ordering = ('-timestamp',)

@admin.register(ShenaseTakhsis)
class ShenaseTakhsisAdmin(admin.ModelAdmin):
    list_display = ('purchase', 'code', 'weight','created_at')
    list_filter = ('created_at',)
    search_fields = ('purchase__purchase_number', 'code')
    ordering = ('-created_at',)


# تنظیمات نمایش مدل Task در ادمین
# @admin.register(Task)
# class TaskAdmin(admin.ModelAdmin):
#     list_display = ('customer', 'description', 'status', 'due_date',  'create_time')
#     list_filter = ('status',)
#     search_fields = ('customer__name', 'description')
#     ordering = ('due_date',)

# تنظیمات نمایش مدل CallSession در ادمین
@admin.register(CallSession)
class CallSessionAdmin(admin.ModelAdmin):
    list_display = ('customer', 'date')
    list_filter = ('date', 'customer__sales_agent')
    ordering = ('-date',)


# تنظیمات نمایش مدل SalesAgent در ادمین
@admin.register(SalesAgent)
class SalesAgentAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'user')
    search_fields = ('name', 'phone_number')
    ordering = ('name',)


# تنظیمات نمایش مدل FinancialManager در ادمین
@admin.register(FinancialManager)
class FinancialManagerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'user')
    search_fields = ('name', 'phone_number')
    ordering = ('name',)

# تنظیمات نمایش مدل LogisticsManager در ادمین
@admin.register(LogisticsManager)
class LogisticsManagerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'user')
    search_fields = ('name', 'phone_number')
    ordering = ('name',)

# @admin.register(PhoneNumber)
# class PhoneNumberAdmin(admin.ModelAdmin):
#     list_display = ('number', 'customer', 'is_primary')
#     list_filter = ('is_primary',)
#     search_fields = ('number', 'customer__name')
#     raw_id_fields = ('customer',)

@admin.register(SupportAgent)
class SupportAgentAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone_number', 'message', 'created_at', 'updated_at')
    search_fields = ('name', 'email', 'phone_number', 'message')
    ordering = ('-created_at',)


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
        
        print(f"آمار پیامک‌ها:")
        print(f"کل: {total}, در انتظار: {pending}, ارسال شده: {sent}, با خطا: {failed}, معلق: {suspended}")
        
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
class BarnamehAdmin(admin.ModelAdmin):
    list_display = ('number', 'purchase_number', 'shenase_takhsis_code', 'serial', 'barnameh_date', 'is_sent_to_bki', 'is_sent_to_bki_at')
    list_filter = ('is_sent_to_bki', 'purchase__customer')
    search_fields = ('number', 'purchase_number', 'shenase_takhsis_code', 'serial')
    ordering = ('-barnameh_date',)


from bki_barnameh.models.BarnamehModel import BarnamehLog
@admin.register(BarnamehLog)
class BarnamehLogAdmin(admin.ModelAdmin):
    list_display = ('barnameh', 'log_date', 'log_message')
    ordering = ('-log_date',)

@admin.register(VaredKonandeh)
class VaredKonandehAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'email', 'vallet')
    search_fields = ('name', 'phone_number', 'email')

@admin.register(Barbary)
class BarbaryAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'email')
    search_fields = ('name', 'phone_number', 'email')





