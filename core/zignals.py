from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from core._models import Purchase, Task, SalesAgent
from django.db import models
from sms_api.apis import queue_sms, send_purchase_status_notification
from sms_api.models import SmsTemplate
import logging
from core.PurchaseModel import PurchaseStateChange

logger = logging.getLogger("core_zignals")


@receiver(post_save, sender=Purchase)
def create_task_for_purchase(sender, instance, created, **kwargs):
    if created:  # فقط اگر Purchase جدید ایجاد شده باشد
        # ایجاد تسک برای ۱۵ دقیقه بعد
        due_date = timezone.now() + timedelta(minutes=15)
        
        # توضیحات تسک
        task_description = f"پیگیری پیامک ارسال شده برای مشتری - کوتاژ {instance.cargo if instance.cargo else 'بدون کوتاژ'}"
        
        # ایجاد تسک
        # چک کردن اینکه آیا کارشناسان فروش مشتری فقط ادمین‌ها هستند یا نه
        sales_agents = instance.customer.sales_agent.all()
        has_non_admin = False
        for agent in sales_agents:
            if not agent.user.is_superuser:
                has_non_admin = True
                break
        
        if has_non_admin:
            Task.objects.create(
                description=task_description,
                customer=instance.customer,  # مشتری مرتبط با خرید
                purchase=instance,  # خرید مرتبط با تسک
                due_date=due_date,  # زمان انجام تسک (۱۵ دقیقه بعد)
                status=False  # تسک به‌صورت پیش‌فرض انجام نشده است
            )

# سیگنال جدید برای ارسال پیامک هنگام ایجاد خرید جدید
@receiver(post_save, sender=Purchase)
def send_sms_on_purchase_create(sender, instance, created, **kwargs):
    """
    ارسال پیامک به مشتری هنگام ایجاد خرید جدید
    """
    logger.debug(f"Initializing SMS sending process for new purchase: {instance.id}")
    if not created:  # فقط اگر Purchase جدید ایجاد شده باشد
        return
    logger.debug(f"New purchase created: {instance.id}, checking SMS conditions")
    
    # اگر مشتری وجود ندارد یا تنظیمات sms_preference غیرفعال است، پیامک ارسال نمی‌شود
    if not instance.customer or not instance.customer.sms_preference:
        logger.info(f"SMS not sent for purchase {instance.id}: Customer does not exist or SMS preference is disabled")
        return
    
    # بررسی اینکه کارشناسان فروش مشتری فقط ادمین‌ها نباشند
    sales_agents = instance.customer.sales_agent.all()
    has_non_admin = False
    for agent in sales_agents:
        if not agent.user.is_superuser:
            has_non_admin = True
            break
    
    if not has_non_admin:
        logger.info(f"SMS not sent for purchase {instance.id}: No non-admin sales agent")
        return
        
    # فقط برای خریدهایی که تنظیم send_cottage_sms آنها فعال است
    if not instance.send_cottage_sms:
        logger.info(f"SMS not sent for purchase {instance.id}: send_cottage_sms is disabled")
        return
    
    # مشاهده وضعیت فعلی خرید
    current_state = instance.state
    logger.info(f"Purchase {instance.id} current state: {current_state}")
    
    try:
        # یافتن قالب پیام برای وضعیت جدید
        template = SmsTemplate.objects.filter(status=current_state, is_active=True).first()
        
        if not template:
            logger.info(f"No active SMS template found for state {current_state} (Purchase ID: {instance.id})")
            return False
            
        # پردازش قالب پیام با استفاده از تابع send_purchase_status_notification
        result = send_purchase_status_notification(instance)
        
        if result:
            logger.info(f"Successfully sent SMS for new purchase {instance.id}")
            
            # ایجاد رکورد تغییر وضعیت
            PurchaseStateChange.objects.create(
                purchase=instance,
                previous_state='INITIATED',
                new_state=current_state,
                sms_sent=True,
                sms_sent_at=timezone.now(),
                notes="ارسال پیامک خودکار برای خرید جدید"
            )
        else:
            logger.warning(f"Failed to send SMS for new purchase {instance.id}")
    
    except Exception as e:
        logger.warning(f"Error processing SMS for new purchase {instance.id}: {str(e)}")


@receiver(post_save, sender=PurchaseStateChange)
def send_sms_on_state_change(sender, instance, created, **kwargs):
    """
    ارسال پیامک به مشتری هنگام تغییر وضعیت خرید
    """
    if not created:  # فقط برای رکوردهای جدید تغییر وضعیت
        logger.debug("Ignoring duplicate state change")
        return
    
    # بررسی اینکه تغییر وضعیت تازه است (کمتر از 1 روز)
    if instance.changed_at:
        time_diff = timezone.now() - instance.changed_at
        if time_diff.days >= 1:
            logger.info(f"State change is older than 1 day, skipping SMS for purchase {instance.purchase.id}")
            return
    
    logger.debug(f"Processing state change to {instance.new_state} for purchase {instance.purchase.id}")

    # اگر پیامک قبلا ارسال شده، دیگر ارسال نکن
    if instance.sms_sent:
        logger.info(f"SMS already sent for state change to {instance.new_state} for purchase {instance.purchase.id}")
        return
    
    purchase = instance.purchase
    new_state = instance.new_state
    
    # اگر مشتری وجود ندارد یا تنظیمات sms_preference غیرفعال است، پیامک ارسال نمی‌شود
    if not purchase.customer or not purchase.customer.sms_preference:
        logger.debug(f"SMS not sent for purchase {purchase.id}: No customer or SMS preference disabled")
        return
    
    # بررسی اینکه کارشناسان فروش مشتری فقط ادمین‌ها نباشند
    sales_agents = purchase.customer.sales_agent.all()
    has_non_admin = False
    for agent in sales_agents:
        if not agent.user.is_superuser:
            has_non_admin = True
            break
    
    if not has_non_admin:
        logger.debug(f"SMS not sent for purchase {purchase.id}: Only admin sales agents")
        return
    
    try:
        # یافتن قالب پیام برای وضعیت جدید
        template = SmsTemplate.objects.filter(status=new_state, is_active=True).first()
        
        if not template:
            logger.info(f"No active SMS template found for state {new_state} (Purchase ID: {purchase.id})")
            return
        
        # پردازش قالب پیام و جایگزینی متغیرها
        message = template.content
        
        # ایجاد یک دیکشنری برای تمام متغیرهای قالب
        template_vars = {}
        
        # متغیرهای مشتری
        if purchase.customer:
            template_vars['customer_name'] = purchase.customer.name
        else:
            template_vars['customer_name'] = ''
        
        # متغیرهای خرید
        template_vars['purchase_number'] = str(purchase.purchase_number or '')
        template_vars['invoice_id'] = str(purchase.invoice_id or '')
        template_vars['order_weight'] = str(purchase.order_weight or '')
        template_vars['customer_price'] = str(purchase.customer_price or '')
        template_vars['amount_paid'] = str(purchase.amount_paid or '')
        template_vars['extelaf_type'] = str(purchase.extelaf_type or '')
        template_vars['extelaf_weight'] = str(purchase.extelaf_weight or '')
        template_vars['extelaf_amount'] = str(purchase.extelaf_amount or '')
        
        # شناسه تخصیص‌ها
        shenase_takhsis_list = purchase.shenase_takhsis_set.all()
        if shenase_takhsis_list.exists():
            shenase_codes = [st.code for st in shenase_takhsis_list if st.code]
            template_vars['shenase_takhsis'] = ', '.join(shenase_codes) if shenase_codes else ''
        else:
            template_vars['shenase_takhsis'] = str(purchase.shenase_takhsis or '')
        
        # اگر اطلاعات بارنامه وجود دارد
        if hasattr(purchase, 'barnameh') and purchase.barnameh:
            template_vars['barnameh'] = str(purchase.barnameh)
        else:
            template_vars['barnameh'] = ''
        
        # جایگزینی متغیرهای کوتاژ
        if purchase.cargo:
            # برای فیلدهای cargo، با getattr بررسی می‌کنیم که آیا فیلد وجود دارد
            cargo = purchase.cargo
            
            # فیلد cottage - در بعضی مدل‌ها ممکن است cottage_number یا cottage باشد
            cottage_value = ''
            for field_name in ['cottage', 'cottage_number', 'cottage_id']:
                if hasattr(cargo, field_name):
                    cottage_value = getattr(cargo, field_name, '')
                    break
            template_vars['cottage'] = str(cottage_value or '')
            
            # سایر فیلدهای cargo
            template_vars['product_type'] = getattr(cargo, 'product_type', '')
            if hasattr(cargo, 'get_product_type_display'):
                template_vars['product_type'] = cargo.get_product_type_display()
            
            template_vars['product_country'] = getattr(cargo, 'country', '')
            if hasattr(cargo, 'get_country_display'):
                template_vars['product_country'] = cargo.get_country_display()
        else:
            template_vars['cottage'] = ''
            template_vars['product_type'] = ''
            template_vars['product_country'] = ''
            
        # اطلاعات کارشناس فروش
        if purchase.customer and purchase.customer.sales_agent.exists():
            agents = purchase.customer.sales_agent.all()
            agent_names = [agent.name for agent in agents if hasattr(agent, 'name') and agent.name]
            agent_phones = [agent.phone_number for agent in agents if hasattr(agent, 'phone_number') and agent.phone_number]
            
            template_vars['sales_agent_name'] = ', '.join(agent_names) if agent_names else ''
            template_vars['sales_agent_phone'] = ', '.join(agent_phones) if agent_phones else ''
        else:
            template_vars['sales_agent_name'] = ''
            template_vars['sales_agent_phone'] = ''
        
        # جایگزینی همه متغیرها در قالب
        for key, value in template_vars.items():
            placeholder = '{{' + key + '}}'
            message = message.replace(placeholder, str(value))
        
        # جمع‌آوری همه شماره‌های تلفن مرتبط
        all_phone_numbers = set()
        
        # شماره‌های مشتری
        customer_phones = purchase.customer.get_all_phone_numbers(purchase, True)
        all_phone_numbers.update(customer_phones)
        
        # شماره بازارگاه
        if purchase.bazaargah_phone_number:
            # پاکسازی شماره بازارگاه
            cleaned_bazaargah = purchase.customer._clean_phone_number(purchase.bazaargah_phone_number)
            if cleaned_bazaargah:
                all_phone_numbers.add(cleaned_bazaargah)
        
        # شماره‌های تحویل از شناسه تخصیص‌ها
        for shenase in purchase.shenase_takhsis_set.all():
            if shenase.tahvil_phone_number:
                cleaned_tahvil = purchase.customer._clean_phone_number(shenase.tahvil_phone_number)
                if cleaned_tahvil:
                    all_phone_numbers.add(cleaned_tahvil)
        
        # شماره تحویل اصلی خرید
        if purchase.tahvil_phone_number:
            cleaned_main_tahvil = purchase.customer._clean_phone_number(purchase.tahvil_phone_number)
            if cleaned_main_tahvil:
                all_phone_numbers.add(cleaned_main_tahvil)
        
        # ارسال پیامک به همه شماره‌ها
        success_count = 0
        for phone in all_phone_numbers:
            try:
                queue_sms(
                    number=phone,
                    message=message,
                    notification_type=new_state,
                    purchase=purchase
                )
                success_count += 1
            except Exception as e:
                logger.warning(f"Error queuing SMS for {phone} (Purchase ID: {purchase.id}): {str(e)}")
        
        if success_count > 0:
            logger.info(f"Successfully queued SMS for state change to {new_state} for purchase {purchase.id} to {success_count} numbers")
            
            # آپدیت فیلد sms_sent در رکورد تغییر وضعیت
            instance.sms_sent = True
            instance.sms_sent_at = timezone.now()
            instance.save(update_fields=['sms_sent', 'sms_sent_at'])
    
    except Exception as e:
        logger.warning(f"Error processing SMS for state change (Purchase ID: {purchase.id}): {str(e)}")