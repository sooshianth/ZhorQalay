from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import logging

from .models.NonBazargahPurchase import NonBazargahPurchase
from .models.Invoice import Invoice
from .models.InvoiceItem import InvoiceItem
from .models.Hazinah import Hazinah

logger = logging.getLogger('major_signals')


@receiver(post_save, sender=NonBazargahPurchase)
def create_invoices_for_closed_purchase(sender, instance, created, **kwargs):
    """
    ایجاد خودکار فاکتور هزینه برای هر بارنامه هنگام بستن خرید خارج بازارگاه
    """
    # فقط وقتی که خرید بسته شده باشد (state = 'purchase_closed')
    if instance.state != 'purchase_closed':
        return
    
    try:
        # دریافت تمام بارنامه‌های مرتبط با این خرید
        barnamehs = instance.get_all_barnamehs()
        
        if not barnamehs:
            logger.warning(f"هیچ بارنامه‌ای برای خرید {instance.id} یافت نشد")
            return
        
        logger.info(f"شروع ایجاد فاکتور برای {len(barnamehs)} بارنامه خرید {instance.id}")
        
        for barnameh in barnamehs:
            # بررسی اینکه آیا قبلاً فاکتور ایجاد شده یا نه
            if Invoice.objects.filter(income=barnameh).exists():
                logger.info(f"فاکتور برای بارنامه {barnameh.id} قبلاً ایجاد شده است")
                continue
            
            # محاسبه وزن خالص بارنامه
            net_weight = None
            if barnameh.loaded_vehicle_weight and barnameh.empty_vehicle_weight:
                net_weight = float(barnameh.loaded_vehicle_weight) - float(barnameh.empty_vehicle_weight)
            
            # اگر وزن خالص موجود نباشد، از وزن نهایی تحویل استفاده کن
            if not net_weight and barnameh.final_delivered_weight:
                net_weight = float(barnameh.final_delivered_weight)
            
            # اگر هنوز وزن موجود نباشد، از وزن بارنامه استفاده کن
            if not net_weight and barnameh.tonnage:
                net_weight = float(barnameh.tonnage) * 1000  # تبدیل تن به کیلوگرم
            
            if not net_weight:
                logger.warning(f"وزن قابل محاسبه برای بارنامه {barnameh.id} یافت نشد")
                continue
            
            # دریافت فی خرید از خرید
            company_price = instance.company_price or 0
            
            # محاسبه مبلغ کل
            total_amount = int(net_weight * company_price)
            
            # ایجاد فاکتور هزینه
            invoice = Invoice.objects.create(
                type='Income',
                income=barnameh,
                issue_date=timezone.now().date(),
                invoice_id=f"{instance.purchase_number or instance.id}{barnameh.number or barnameh.id}",
                description=f"فاکتور برای بارنامه {barnameh.number or barnameh.id} - خرید {instance.purchase_number or instance.id}",
                customer=instance.customer
            )
            
            # ایجاد آیتم فاکتور
            InvoiceItem.objects.create(
                invoice=invoice,
                product_type='NonBazargah',
                non_bazargah_product=instance.product,
                price=company_price,
                amount=int(net_weight)
            )
            
            logger.info(f"فاکتور {invoice.invoice_id} برای بارنامه {barnameh.id} ایجاد شد - وزن: {net_weight} کیلوگرم، مبلغ: {total_amount:,} ریال")
        
        logger.info(f"تمام فاکتورهای خرید {instance.id} با موفقیت ایجاد شدند")
        
    except Exception as e:
        logger.error(f"خطا در ایجاد فاکتور برای خرید {instance.id}: {str(e)}")
        # در صورت خطا، لاگ کنید اما برنامه را متوقف نکنید
