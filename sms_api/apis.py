from sms_ir import SmsIr
from .models import SmsLog


api_key='mbdRODVCB2JHUX5c3IpetXsiDXFIT6bo7JZo0PhiTFWkuIN4'
linenumber=90008316


sms_account = SmsIr(api_key, linenumber)
def send_instant_sms(number:str, message:str, linenumber=linenumber, sms_account=sms_account):
    try:
        result = sms_account.send_sms(number, message, linenumber)
        SmsLog.objects.create(
            recipient_number=number,
            message=message
        )
        return result
    except Exception as e:
        print(f"SMS sending error: {e}")
        return None

def todays_sms_report(sms_account=sms_account):
    return sms_account.report_today(
        page_size=20,
        page_number=15,
        )

# Purchase notification functions
def send_new_purchase_notification(purchase):
    """
    Send SMS notification when a new purchase is created
    """
    if not purchase.customer.sms_preference:
        return False
    
    number = purchase.customer.phone_number
    if not number.startswith('09'):
        number = '0' + number
    
    cargo = purchase.cargo
    product_name = cargo.get_product_type_display()
    country = cargo.get_country_display()
    
    message = (
        f"اطلاعات محصول درخواستی شما:\n"
        f"{product_name} {country}\n"
        f"قیمت هر کیلو: {cargo.customer_price} ریال\n"
        f"\n"
        f"کوتاژ: {cargo.cottage}\n"
        f"\n"

        f"شما درخواست این محصول به وزن {purchase.weight} کیلوگرم و مبلغ کل {cargo.customer_price * purchase.weight} ریال را ثبت کردید.\n"
        f"وارد سامانه بازارگاه شده و با استفاده از کوتاژ فوق خرید {purchase.payment_method} خود را انجام دهید و سپس رسید را برای کارشناسان ما ارسال کنید\n"
        f"شرکت تأمین نهاده سیمرغ"
    )
    
    return send_instant_sms(number, message)

def send_payment_confirmation(purchase):
    """
    Send SMS notification when purchase is financially approved
    """
    if not purchase.customer.sms_preference:
        return False
    
    number = purchase.customer.phone_number
    if not number.startswith('09'):
        number = '0' + number
    
    message = (
        f"مشتری گرامی {purchase.customer.phone_number}،\n"
        f"پرداخت شما برای سفارش {purchase.purchase_number} تأیید شد.\n"
        f"به زودی اطلاعات ارسال برای شما پیامک می‌شود.\n"
        f"شرکت تأمین نهاده سیمرغ"
    )
    
    return send_instant_sms(number, message)

def send_address_notification(purchase):
    """
    Send SMS notification when address is sent to importer
    """
    if not purchase.customer.sms_preference:
        return False
    
    number = purchase.customer.phone_number
    if not number.startswith('09'):
        number = '0' + number
    
    message = (
        f"مشتری گرامی \n"
        f"آدرس ارسال برای سفارش {purchase.purchase_number} به باربری ارسال شد.\n"
        f"به زودی شماره بارنامه برای شما پیامک می‌شود.\n"
        f"شرکت تأمین نهاده سیمرغ"
    )
    
    return send_instant_sms(number, message)

def send_barnameh_notification(purchase):
    """
    Send SMS notification when shipping info (barnameh) is issued
    """
    if not purchase.customer.sms_preference:
        return False
    
    number = purchase.customer.phone_number
    if not number.startswith('09'):
        number = '0' + number
    
    shenase_list = "\n".join([s.shenase for s in purchase.shenase_takhsis.all()])
    
    message = (
        f"مشتری گرامی\n"
        f"بارنامه برای سفارش {purchase.purchase_number} صادر شد.\n"
        f"شناسه‌های تخصیص:\n{shenase_list}\n"
        f"به زودی محموله شما ارسال خواهد شد.\n"
        f"شرکت تأمین نهاده سیمرغ"
    )
    
    return send_instant_sms(number, message)

def send_extelaf_notification(purchase):
    """
    Send SMS notification when there's a weight difference (extelaf) of type "sarak"
    """
    if not purchase.customer.sms_preference or purchase.extelaf_type != 'سرک':
        return False
    
    number = purchase.customer.phone_number
    if not number.startswith('09'):
        number = '0' + number
    
    message = (
        f"مشتری گرامی {purchase.customer.phone_number}،\n"
        f"سفارش {purchase.purchase_number} با اختلاف وزن (سرک) به میزان {purchase.extelaf_weight} کیلوگرم "
        f"تحویل شده است.\n"
        f"وزن اختلاف: {purchase.extelaf_weight} کیلوگرم\n"
        f"مبلغ قابل پرداخت: {purchase.extelaf_amount} ریال\n"
        f"لطفا نسبت به پرداخت مبلغ اقدام فرمایید.\n"
        f"شرکت تأمین نهاده سیمرغ"
    )
    
    return send_instant_sms(number, message)

