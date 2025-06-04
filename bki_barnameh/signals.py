from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from sms_api.apis import queue_sms
from sms_api.models import SmsTemplate
import logging
from .models.BarnamehModel import Barnameh

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Barnameh)
def send_sms_on_barnameh_create(sender, instance, created, **kwargs):
    """
    ارسال پیامک به راننده و مشتری هنگام ایجاد بارنامه جدید
    """
    if not created:  # فقط اگر Barnameh جدید ایجاد شده باشد
        return
    
    logger.info(f"New barnameh created: {instance.id}, checking SMS conditions")
    
    # جمع‌آوری شماره‌های تلفن برای ارسال پیامک
    phone_numbers = []
    
    # اضافه کردن شماره راننده (اگر وجود دارد)
    if instance.driver_phone:
        # پاک کردن فاصله‌ها و کاراکترهای اضافی
        driver_phone = instance.driver_phone.strip().replace(' ', '').replace('-', '')
        if driver_phone:
            phone_numbers.append(driver_phone)
            logger.info(f"Added driver phone {driver_phone} for barnameh {instance.id}")
    
    # اضافه کردن شماره‌های مشتری (از طریق Purchase)
    if instance.purchase and instance.purchase.customer:
        customer = instance.purchase.customer
        
        # بررسی تنظیمات SMS مشتری
        if customer.sms_preference:
            # بررسی اینکه کارشناسان فروش مشتری فقط ادمین‌ها نباشند
            sales_agents = customer.sales_agent.all()
            has_non_admin = False
            for agent in sales_agents:
                if not agent.user.is_superuser:
                    has_non_admin = True
                    break
            
            if has_non_admin:
                # اضافه کردن همه شماره‌های مشتری
                customer_phones = customer.get_all_phone_numbers()
                for phone in customer_phones:
                    if phone and phone not in phone_numbers:
                        phone_numbers.append(phone)
                        logger.info(f"Added customer phone {phone} for barnameh {instance.id}")
            else:
                logger.warning(f"Customer SMS not sent for barnameh {instance.id}: No non-admin sales agent")
        else:
            logger.warning(f"Customer SMS not sent for barnameh {instance.id}: SMS preference is disabled")
    
    if not phone_numbers:
        logger.warning(f"No phone numbers found for barnameh {instance.id}")
        return
    
    try:
        # یافتن قالب پیام برای بارنامه جدید
        template = SmsTemplate.objects.filter(status='BARNAMEH_CREATED', is_active=True).first()
        
        if not template:
            logger.warning(f"No active SMS template found for BARNAMEH_CREATED status (Barnameh ID: {instance.id})")
            return
        
        # پردازش قالب پیام و جایگزینی متغیرها
        message = template.content
        
        # ایجاد یک دیکشنری برای تمام متغیرهای قالب
        template_vars = {}
        
        # متغیرهای بارنامه
        template_vars['barnameh_number'] = str(instance.number or '')
        template_vars['barnameh_serial'] = str(instance.serial or '')
        template_vars['driver_name'] = str(instance.driver_name or '')
        template_vars['driver_phone'] = str(instance.driver_phone or '')
        template_vars['vehicle_plate'] = str(instance.vehicle_plate or '')
        template_vars['receiver_name'] = str(instance.receiver_name or '')
        template_vars['destination'] = str(instance.destination or '')
        template_vars['tonnage'] = str(instance.tonnage or '')
        
        # متغیرهای مشتری (در صورت وجود)
        if instance.purchase and instance.purchase.customer:
            customer = instance.purchase.customer
            template_vars['customer_name'] = customer.name
            
            # متغیرهای خرید
            purchase = instance.purchase
            template_vars['purchase_number'] = str(purchase.purchase_number or '')
            template_vars['invoice_id'] = str(purchase.invoice_id or '')
            template_vars['order_weight'] = str(purchase.order_weight or '')
            template_vars['customer_price'] = str(purchase.customer_price or '')
            
            # متغیرهای کوتاژ
            if purchase.cargo:
                cargo = purchase.cargo
                
                # فیلد cottage
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
            if customer.sales_agent.exists():
                agents = customer.sales_agent.all()
                agent_names = [agent.name for agent in agents if hasattr(agent, 'name') and agent.name]
                agent_phones = [agent.phone_number for agent in agents if hasattr(agent, 'phone_number') and agent.phone_number]
                
                template_vars['sales_agent_name'] = ', '.join(agent_names) if agent_names else ''
                template_vars['sales_agent_phone'] = ', '.join(agent_phones) if agent_phones else ''
            else:
                template_vars['sales_agent_name'] = ''
                template_vars['sales_agent_phone'] = ''
        else:
            # اگر اطلاعات مشتری وجود ندارد، متغیرها را خالی تنظیم کن
            template_vars['customer_name'] = ''
            template_vars['purchase_number'] = ''
            template_vars['invoice_id'] = ''
            template_vars['order_weight'] = ''
            template_vars['customer_price'] = ''
            template_vars['cottage'] = ''
            template_vars['product_type'] = ''
            template_vars['product_country'] = ''
            template_vars['sales_agent_name'] = ''
            template_vars['sales_agent_phone'] = ''
        
        # جایگزینی همه متغیرها در قالب
        for key, value in template_vars.items():
            placeholder = '{{' + key + '}}'
            message = message.replace(placeholder, str(value))
        
        # ارسال پیامک به همه شماره‌ها
        success_count = 0
        for phone in phone_numbers:
            try:
                queue_sms(
                    number=phone,
                    message=message,
                    notification_type='BARNAMEH_CREATED',
                    purchase=instance.purchase  # در صورت وجود
                )
                success_count += 1
                logger.info(f"Successfully queued SMS for barnameh {instance.id} to {phone}")
            except Exception as e:
                logger.error(f"Error queuing SMS for {phone} (Barnameh ID: {instance.id}): {str(e)}")
        
        if success_count > 0:
            logger.info(f"Successfully queued SMS for new barnameh {instance.id} to {success_count} numbers")
        else:
            logger.warning(f"Failed to queue SMS for any numbers for barnameh {instance.id}")
    
    except Exception as e:
        logger.exception(f"Error processing SMS for new barnameh {instance.id}: {str(e)}") 