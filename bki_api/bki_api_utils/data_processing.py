"""
Purchase Data Processing
=======================

Functions for processing purchase data from the BKI API.
"""

from django.contrib.auth.models import User
from core.PurchaseModel import Purchase, ShenaseTakhsis
from core.CustomerModel import Customer, PhoneNumber
from core.CargoProductModel import CargoProduct
from core.SalesAgentModel import SalesAgent
from .helpers import clean_phone_number, determine_product_type, update_incorrect_phone_numbers
from .location import get_province_name
import jdatetime
from django.utils import timezone
import logging

logger = logging.getLogger("bki_api_data_processing")

def get_state_priority(state):
    """
    Get the priority/order of a purchase state in the workflow.
    Higher numbers represent later stages in the purchase process.
    
    Args:
        state (str): The purchase state
        
    Returns:
        int: The priority order of the state
    """
    state_priorities = {
        'INITIATED': 1,
        'SMS_SENT': 2,
        'PAYMENT_VERIFIED': 3,
        'ALLOCATION_APPROVED': 4,
        'ADDRESS_SENT': 5,
        'WAITING_FOR_BARNAMEH': 6,
        'BARNAMEH_INCOMPLETE': 7,
        'BARNAMEH_ISSUED': 8,
        'PURCHASE_CLOSED': 9,
        'PAY_KASRI': 10,
        'RECIEIVE_SARAK': 11,
        'FULLY_SETTLED': 12,
        'INVOICE_ISSUED': 13,
        'CANCELED': 99,  # Special state
        'ARCHIVED': 100,  # Special state
    }
    return state_priorities.get(state, 0)


def is_state_progression(current_state, new_state):
    """
    Check if changing from current_state to new_state represents progress.
    اجازه جهش (jump) داده می‌شود، فقط برگشت به عقب ممنوع است.
    
    Args:
        current_state (str): The current state of the purchase
        new_state (str): The proposed new state
        
    Returns:
        bool: True if the change represents progress, False otherwise
    """
    current_priority = get_state_priority(current_state)
    new_priority = get_state_priority(new_state)
    
    # Special cases:
    # - BARNAMEH_INCOMPLETE can go back to BARNAMEH_ISSUED (completion of incomplete barnameh)
    if current_state == 'BARNAMEH_INCOMPLETE' and new_state == 'BARNAMEH_ISSUED':
        return True
    
    # - PAY_KASRI and RECIEIVE_SARAK can both progress to FULLY_SETTLED
    if current_state in ['PAY_KASRI', 'RECIEIVE_SARAK'] and new_state == 'FULLY_SETTLED':
        return True
    
    # اجازه جهش: خرید می‌تواند چندین مرحله را یکباره طی کند
    # فقط برگشت به عقب ممنوع است (new_priority >= current_priority)
    # مگر در حالت‌های خاص بالا
    return new_priority >= current_priority


def can_api_update_state(current_state, new_state):
    """
    Check if the API is allowed to update the state from current to new.
    Some states can only be changed by operators, not by API.
    
    Args:
        current_state (str): The current state of the purchase
        new_state (str): The proposed new state from API
        
    Returns:
        bool: True if API can make this change, False otherwise
    """
    # States that are only managed by operators (not API)
    operator_only_states = {
        'ADDRESS_SENT',
        'WAITING_FOR_BARNAMEH',
        'PAY_KASRI',
        'RECIEIVE_SARAK',
        'FULLY_SETTLED',
        'INVOICE_ISSUED',
        'CANCELED',
        'ARCHIVED'
    }
    
    # If current state is operator-only, API cannot change it
    if current_state in operator_only_states:
        return False
    
    # If new state is operator-only, API cannot set it
    if new_state in operator_only_states:
        return False
    
    # API can only make progressive changes
    return is_state_progression(current_state, new_state)


def log_state_change_attempt(purchase_number, current_state, suggested_state, allowed, reason=""):
    """
    Log state change attempts with appropriate messages.
    
    Args:
        purchase_number (str): The purchase number
        current_state (str): Current state of the purchase
        suggested_state (str): State suggested by API
        allowed (bool): Whether the change was allowed
        reason (str): Additional reason for the decision
    """
    current_display = get_state_display_name(current_state)
    suggested_display = get_state_display_name(suggested_state)
    
    if allowed:
        logger.info(f"✅ خرید {purchase_number}: وضعیت از '{current_display}' به '{suggested_display}' تغییر کرد")
    else:
        logger.warning(f"⚠️ خرید {purchase_number}: تغییر وضعیت از '{current_display}' به '{suggested_display}' مجاز نیست {reason}")


def get_state_display_name(state):
    """
    Get the Persian display name for a purchase state.
    
    Args:
        state (str): The state code
        
    Returns:
        str: The Persian display name
    """
    state_names = {
        'INITIATED': 'شروع شده',
        'SMS_SENT': 'پیامک ارسال شده',
        'PAYMENT_VERIFIED': 'ثبت خرید در بازارگاه',
        'ALLOCATION_APPROVED': 'ثبت تخصیص در بازارگاه',
        'ADDRESS_SENT': 'ارسال آدرس به واردکننده',
        'WAITING_FOR_BARNAMEH': 'در انتظار بارنامه',
        'BARNAMEH_INCOMPLETE': 'صدور بارنامه (ناقص)',
        'BARNAMEH_ISSUED': 'صدور بارنامه',
        'PURCHASE_CLOSED': 'بستن خرید در بازارگاه',
        'PAY_KASRI': 'پرداخت کسری',
        'RECIEIVE_SARAK': 'دریافت سرک',
        'FULLY_SETTLED': 'تسویه کامل',
        'INVOICE_ISSUED': 'صدور فاکتور',
        'CANCELED': 'لغو شده',
        'ARCHIVED': 'آرشیو شده',
    }
    return state_names.get(state, state)


def create_or_get_customer(buyer_name, buyer_phone, buyer_address, province_code):
    """
    Create a new customer or get an existing one based on phone number.
    
    Args:
        buyer_name (str): The name of the buyer
        buyer_phone (str): The phone number of the buyer
        buyer_address (str): The address of the buyer
        province_code (str): The province code of the buyer
        
    Returns:
        tuple: (customer, created, error_message)
            - customer: The Customer object created or found
            - created: True if a new customer was created, False otherwise
            - error_message: An error message if the operation failed, None otherwise
    """
    # Clean the phone number
    clean_phone, error = clean_phone_number(buyer_phone)
    if error:
        logger.warning(f"توجه: {error}")
    
    # Search for the customer by phone number
    customer = None
    created = False
    
    try:
        # Search in phone numbers
        phone = PhoneNumber.objects.filter(number=clean_phone).first()
        if phone:
            customer = phone.customer
            customer = Customer.objects.filter(name=buyer_name).first()
    except Exception as e:
        return None, False, f"خطا در جستجوی مشتری با شماره تلفن: {str(e)}"
    
    # If no customer was found, create a new one
    if not customer:
        try:
            # Determine the province name
            province_name = get_province_name(province_code) or 'نامشخص'
            
            # Create a new customer with valid fields according to the model
            customer = Customer.objects.create(
                name=buyer_name,
                city=province_name
            )
            
            # Add address and origin after creating the object
            if hasattr(customer, 'address'):
                customer.address = buyer_address
            if hasattr(customer, 'origin'):
                customer.origin = 'bazaargah'
            customer.save()
            
            # Create a phone number for the customer
            PhoneNumber.objects.create(
                customer=customer,
                number=clean_phone,
                is_primary=True
            )
            
            # Assign a default sales agent (superuser) to the new customer
            assign_default_sales_agent(customer)
            
            created = True
            
            return customer, created, None
        except Exception as e:
            return None, False, f"خطا در ایجاد مشتری جدید: {str(e)}"
    
    return customer, created, None


def assign_default_sales_agent(customer):
    """
    Assign a default sales agent (superuser) to a customer.
    
    Args:
        customer: The Customer object to assign an agent to
        
    Returns:
        bool: True if the assignment was successful, False otherwise
    """
    try:
        # Find a user with superuser access
        admin_users = User.objects.filter(is_superuser=True)
        if admin_users.exists():
            admin_user = admin_users.first()
            # Find or create a sales agent linked to the admin user
            admin_agent, created = SalesAgent.objects.get_or_create(
                user=admin_user,
                defaults={
                    'name': 'مدیریت',
                    'factor_code': '99'  # Default code for the admin
                }
            )
            # Add the sales agent to the customer
            customer.sales_agent.add(admin_agent)
            logger.info(f"کارشناس فروش مدیریت به مشتری {customer.name} اضافه شد")
            return True
    except Exception as e:
        logger.error(f"خطا در اختصاص کارشناس فروش به مشتری: {str(e)}")
        return False


def create_or_get_product(product_name, goodtag, fee):
    """
    Create a new product or get an existing one based on goodtag.
    
    Args:
        product_name (str): The name of the product
        goodtag (str): The cottage code (goodtag) of the product
        fee (int): The price of the product
        
    Returns:
        tuple: (product, created, error_message)
            - product: The CargoProduct object created or found
            - created: True if a new product was created, False otherwise
            - error_message: An error message if the operation failed, None otherwise
    """
    product_type = determine_product_type(product_name)
    cargo = None
    created = False
    
    # Check for goodtag and use it
    if goodtag:
        try:
            # Search for product with goodtag
            cargo = CargoProduct.objects.filter(cottage=goodtag).first()
            
            # If no product with this goodtag was found, create it
            if not cargo:
                cargo = CargoProduct.objects.create(
                    product_type=product_type,
                    cottage=goodtag,
                    customer_price=fee,
                    company_price=fee,
                    weight=1000000,  # Default value
                    type='bazaargah',
                    country='australia'  # Default to Australia
                )
                created = True
                logger.info(f"محصول جدید با کوتاژ {goodtag} و نوع {product_type} ایجاد شد")
        except Exception as e:
            return None, False, f"خطا در ایجاد محصول با کوتاژ {goodtag}: {str(e)}"
    
    # If no product was found based on goodtag, use the previous method
    if not cargo:
        try:
            cargo = CargoProduct.objects.filter(
                product_type=product_type,
                type='bazaargah'
            ).first()
            
            if not cargo:
                # Create a new product if not found
                cargo = CargoProduct.objects.create(
                    product_type=product_type,
                    customer_price=fee,
                    company_price=fee,
                    weight=1000000,  # Default value
                    type='bazaargah',
                    country='australia'  # Default to Australia
                )
                created = True
        except Exception as e:
            return None, False, f"خطا در یافتن یا ایجاد محصول: {str(e)}"
    
    return cargo, created, None


def update_purchase(purchase, purchase_data):
    """
    Update an existing purchase with new data.
    
    Args:
        purchase: The Purchase object to update
        purchase_data (dict): The new purchase data from the API
        
    Returns:
        tuple: (purchase, error_message)
            - purchase: The updated Purchase object
            - error_message: An error message if the update failed, None otherwise
    """
    try:
        # Extract key fields
        qty = int(purchase_data.get('qty', 0) or 0)  # allocation weight (takhsisweight)
        wbarnameshode = int(purchase_data.get('wbarnameshode', 0) or 0)  # delivered weight
        takhsisid = purchase_data.get('allocationid')  # allocation ID
        buyer_name = purchase_data.get('buyername')
        buyer_phone = purchase_data.get('buyerphone')
        buyer_address = purchase_data.get('buyeraddress')
        payment_type = purchase_data.get('paymentterm', 'نقدی')
        fee = int(purchase_data.get('fee', 0) or 0)
        total_value = int(purchase_data.get('totalvalue', 0) or 0)  # مبلغ کل پرداختی
        receiver_phone = purchase_data.get('receiverphone')  # شماره تلفن تحویل
        trace_code = purchase_data.get('tracecode')  # شماره پیگیری
        receiver_id = purchase_data.get('receiverid')  # کد ملی تحویل
        purchase_date = purchase_data.get('date')  # تاریخ خرید به فرمت جلالی (مثلا 1404/02/22)
        total_weight = int(purchase_data.get('totalweight', 0) or 0)  # وزن کل
        
        # Update purchase fields - بدون به‌روزرسانی وزن‌ها
        purchase.buyer_name = buyer_name
        purchase.address = buyer_address
        purchase.bazaargah_phone_number = buyer_phone
        purchase.payment_method = payment_type
        purchase.customer_price = fee
        purchase.amount_paid = total_value
        purchase.tahvil_phone_number = receiver_phone
        purchase.tracking_number = trace_code
        purchase.code_melli_tahvil = receiver_id
        
        # تنظیم فیلد bazaargah_customer نیز برای خریدهای موجود
        if purchase.customer and not purchase.bazaargah_customer:
            purchase.bazaargah_customer = purchase.customer
        
        # Don't overwrite order_weight and delivered_weight here
        # They will be calculated from the sum of all entries in process_grouped_purchase_data
        
        # تبدیل تاریخ جلالی به فرمت مناسب
        if purchase_date:
            try:
                # تبدیل رشته تاریخ به شی jdatetime
                j_date_parts = purchase_date.split('/')
                if len(j_date_parts) == 3:
                    jyear = int(j_date_parts[0])
                    jmonth = int(j_date_parts[1])
                    jday = int(j_date_parts[2])
                    jdate = jdatetime.date(jyear, jmonth, jday)
                    # تنظیم ساعت فعلی
                    now = timezone.now()
                    # ایجاد datetime ترکیبی
                    purchase.created_at = jdatetime.datetime(
                        jyear, jmonth, jday, 
                        now.hour, now.minute, now.second, 
                        tzinfo=now.tzinfo
                    )
            except Exception as e:
                logger.error(f"خطا در تبدیل تاریخ: {str(e)}")
        
        # اگر کارشناس فروش یکتا تنظیم نشده، آن را به مدیریت تنظیم کن
        if not purchase.unique_sales_agent:
            try:
                # یافتن اولین کاربر مدیر
                admin_user = User.objects.filter(is_superuser=True).first()
                if admin_user:
                    # یافتن یا ایجاد کارشناس فروش مدیریت
                    admin_sales_agent, created = SalesAgent.objects.get_or_create(
                        user=admin_user,
                        defaults={
                            'name': 'مدیریت',
                            'factor_code': '99'
                        }
                    )
                    purchase.unique_sales_agent = admin_sales_agent
                    purchase.unique_sales_agent_code = admin_sales_agent.factor_code
            except Exception as e:
                logger.error(f"خطا در تنظیم کارشناس فروش مدیریت برای خرید موجود: {str(e)}")

        # Save changes
        purchase.save()
        
        # Process allocation ID
        if takhsisid and takhsisid != '0':
            # Check if the allocation ID already exists
            if not ShenaseTakhsis.objects.filter(purchase=purchase, code=takhsisid).exists():
                # Create a new allocation ID with the correct weight
                ShenaseTakhsis.objects.create(
                    purchase=purchase,
                    code=takhsisid,
                    weight=qty  # Use the allocation weight (takhsisweight)
                )
        
        return purchase, None
    
    except Exception as e:
        return purchase, f"خطا در به‌روزرسانی خرید: {str(e)}"


def create_purchase(purchase_data):
    """
    Create a new purchase from API data.
    
    Args:
        purchase_data (dict): The purchase data from the API
        
    Returns:
        tuple: (purchase, error_message)
            - purchase: The created Purchase object
            - error_message: An error message if the creation failed, None otherwise
    """
    try:
        # Extract purchase ID
        purchase_number = purchase_data.get('idkharid')
        if not purchase_number:
            return None, "شناسه خرید در داده‌ها یافت نشد"
        
        # Extract key fields
        qty = int(purchase_data.get('qty', 0) or 0)  # allocation weight (takhsisweight)
        wbarnameshode = int(purchase_data.get('wbarnameshode', 0) or 0)  # delivered weight
        takhsisid = purchase_data.get('allocationid')  # allocation ID
        goodtag = purchase_data.get('goodtag')  # cottage code
        
        # Extract other fields
        buyer_name = purchase_data.get('buyername')
        buyer_phone = purchase_data.get('buyerphone')
        buyer_address = purchase_data.get('buyeraddress')
        province_code = purchase_data.get('provincename')
        product_name = purchase_data.get('productname')
        payment_type = purchase_data.get('paymentterm', 'نقدی')
        fee = int(purchase_data.get('fee', 0) or 0)
        total_value = int(purchase_data.get('totalvalue', 0) or 0)  # مبلغ کل پرداختی
        receiver_phone = purchase_data.get('receiverphone')  # شماره تلفن تحویل
        trace_code = purchase_data.get('tracecode')  # شماره پیگیری
        receiver_id = purchase_data.get('receiverid')  # کد ملی تحویل
        purchase_date = purchase_data.get('date')  # تاریخ خرید به فرمت جلالی (مثلا 1404/02/22)
        total_weight = int(purchase_data.get('totalweight', 0) or 0)  # وزن کل
        
        # Calculate weight difference
        weight_diff = 0
        extelaf_type = None
        extelaf_weight = 0
        
        if wbarnameshode > 0 and qty > 0:
            weight_diff = wbarnameshode - qty
            
            if abs(weight_diff) < 5000:  # Difference less than 5000 kg
                if weight_diff > 0:
                    extelaf_type = "سرک"
                elif weight_diff < 0:
                    extelaf_type = "کسری"
                extelaf_weight = abs(weight_diff)
        
        # Determine purchase state - فقط حالت‌های مجاز برای API
        api_determined_state = determine_purchase_state(purchase_data)
        
        # برای خریدهای جدید، API می‌تواند هر وضعیت مجازی را تنظیم کند
        # اما فقط وضعیت‌هایی که توسط API قابل مدیریت هستند
        operator_only_states = {
            'ADDRESS_SENT', 'WAITING_FOR_BARNAMEH', 'PAY_KASRI', 
            'RECIEIVE_SARAK', 'FULLY_SETTLED', 'INVOICE_ISSUED', 
            'CANCELED', 'ARCHIVED'
        }
        
        if api_determined_state in operator_only_states:
            # اگر API وضعیت اپراتور-محور پیشنهاد داد، به جای آن حالت قبلی مناسب را قرار بده
            if api_determined_state in ['PAY_KASRI', 'RECIEIVE_SARAK', 'FULLY_SETTLED']:
                purchase_state = 'PURCHASE_CLOSED'  # قبل از تسویه، خرید بسته شده
            elif api_determined_state in ['CANCELED', 'ARCHIVED']:
                purchase_state = 'INITIATED'  # حالت اولیه
            else:
                purchase_state = 'PAYMENT_VERIFIED'  # حالت پیش‌فرض امن
            logger.warning(f"⚠️ API وضعیت اپراتور-محور {api_determined_state} پیشنهاد داد، به جای آن {purchase_state} تنظیم شد")
        else:
            purchase_state = api_determined_state
        
        # Create or get customer
        customer, _, error = create_or_get_customer(
            buyer_name=buyer_name,
            buyer_phone=buyer_phone,
            buyer_address=buyer_address,
            province_code=province_code
        )
        
        if error:
            return None, error
        
        # Create or get product
        cargo, _, error = create_or_get_product(
            product_name=product_name,
            goodtag=goodtag,
            fee=fee
        )
        
        if error:
            return None, error
        
        # پیدا کردن کارشناس فروش مدیریت
        admin_sales_agent = None
        admin_sales_agent_name = None
        try:
            # یافتن اولین کاربر مدیر
            admin_user = User.objects.filter(is_superuser=True).first()
            if admin_user:
                # یافتن یا ایجاد کارشناس فروش مدیریت
                admin_sales_agent, created = SalesAgent.objects.get_or_create(
                    user=admin_user,
                    defaults={
                        'name': 'مدیریت',
                        'factor_code': '99'
                    }
                )
                admin_sales_agent_name = admin_sales_agent.name
        except Exception as e:
            logger.error(f"خطا در پیدا کردن کارشناس فروش مدیریت: {str(e)}")

        # تنظیم پارامترهای پایه برای ایجاد خرید - بدون تنظیم وزن‌ها
        purchase_params = {
            'purchase_number': purchase_number,
            'customer': customer,
            'bazaargah_customer': customer,  # اضافه کردن مشتری به فیلد bazaargah_customer نیز
            'cargo': cargo,
            'buyer_name': buyer_name,
            'bazaargah_phone_number': buyer_phone,
            'address': buyer_address,
            'order_weight': 0,  # Will be updated in process_grouped_purchase_data
            'delivered_weight': 0,  # Will be updated in process_grouped_purchase_data
            'customer_price': fee,
            'payment_method': payment_type,
            'type': 'bazaargah',
            'state': purchase_state,
            'extelaf_type': None,  # Will be calculated later
            'extelaf_weight': 0,
            'extelaf_amount': 0,
            'amount_paid': total_value,
            'tahvil_phone_number': receiver_phone,
            'tracking_number': trace_code,
            'code_melli_tahvil': receiver_id,
            # تنظیم کارشناس فروش یکتا به مدیریت به صورت پیش‌فرض
            'unique_sales_agent': admin_sales_agent,
            'unique_sales_agent_code': admin_sales_agent.factor_code if admin_sales_agent else None,
        }
        
        # تبدیل تاریخ جلالی به فرمت مناسب
        if purchase_date:
            try:
                # تبدیل رشته تاریخ به شی jdatetime
                j_date_parts = purchase_date.split('/')
                if len(j_date_parts) == 3:
                    jyear = int(j_date_parts[0])
                    jmonth = int(j_date_parts[1])
                    jday = int(j_date_parts[2])
                    jdate = jdatetime.date(jyear, jmonth, jday)
                    # تنظیم ساعت فعلی
                    now = timezone.now()
                    # ایجاد datetime ترکیبی
                    purchase_params['created_at'] = jdatetime.datetime(
                        jyear, jmonth, jday, 
                        now.hour, now.minute, now.second, 
                        tzinfo=now.tzinfo
                    )
            except Exception as e:
                logger.error(f"خطا در تبدیل تاریخ: {str(e)}")
        
        # Create a new purchase
        purchase = Purchase.objects.create(**purchase_params)
        
        # Create allocation ID
        if takhsisid and takhsisid != '0':
            ShenaseTakhsis.objects.create(
                purchase=purchase,
                code=takhsisid,
                weight=qty  # Use the allocation weight (takhsisweight)
            )
        
        return purchase, None
    
    except Exception as e:
        return None, f"خطا در ایجاد خرید: {str(e)}"


def determine_purchase_state(purchase_data):
    """
    Determine the state of a purchase based on its data.
    
    Args:
        purchase_data (dict): The purchase data from the API
        
    Returns:
        str: The determined purchase state
    """
    # Extract key fields
    qty = int(purchase_data.get('qty', 0) or 0)  # order weight (takhsisweight)
    wbarnameshode = int(purchase_data.get('wbarnameshode', 0) or 0)  # delivered weight
    wbarnamenashode = int(purchase_data.get('wbarnamenashode', 0) or 0)  # remaining weight
    takhsisid = purchase_data.get('allocationid')  # allocation ID
    totalweight = int(purchase_data.get('totalweight', 0) or 0)  # total weight
    
    # Calculate weight difference
    weight_diff = 0
    if wbarnameshode > 0 and qty > 0:
        weight_diff = wbarnameshode - qty
    
    # Default state
    purchase_state = 'PAYMENT_VERIFIED'
    
    # Check if allocation ID exists
    if takhsisid and takhsisid != '0':
        purchase_state = 'ALLOCATION_APPROVED'
        
        # Check if barnameh has been issued
        if wbarnameshode > 0:
            if abs(weight_diff) < 5000:
                purchase_state = 'BARNAMEH_ISSUED'
            else:
                purchase_state = 'BARNAMEH_INCOMPLETE'
                
            # Check if purchase is closed
            # Note: For purchases with multiple allocations, this will be overridden
            # in process_grouped_purchase_data with the correct logic
            if totalweight > 0 and totalweight == wbarnameshode:
                purchase_state = 'PURCHASE_CLOSED'
                logger.debug(f"Debug - Purchase state determined as CLOSED: totalweight={totalweight}, wbarnameshode={wbarnameshode}")
    
    return purchase_state


def process_purchase_data(purchase_data, create_if_not_exists=True):
    """
    Process purchase data from the BKI API and update or create a purchase record.
    
    Args:
        purchase_data (dict): The purchase data from the API
        create_if_not_exists (bool): Whether to create a new purchase if it doesn't exist
        
    Returns:
        tuple: (purchase, created, error_message)
            - purchase: The Purchase object created or updated
            - created: True if a new purchase was created, False otherwise
            - error_message: An error message if the operation failed, None otherwise
    """
    # Try to update any phone numbers that were previously incorrectly stored as "9000000000"
    if isinstance(purchase_data, dict):
        updated_count, error_count = update_incorrect_phone_numbers(purchase_data)
        if updated_count > 0:
            logger.info(f"تعداد {updated_count} شماره تلفن نادرست به‌روزرسانی شد")
    
    # If purchase_data is a list, process it as a group
    if isinstance(purchase_data, list):
        # For each item in the list, try to update incorrect phone numbers
        for item in purchase_data:
            updated_count, error_count = update_incorrect_phone_numbers(item)
            if updated_count > 0:
                logger.info(f"تعداد {updated_count} شماره تلفن نادرست به‌روزرسانی شد")
        
        return process_grouped_purchase_data(purchase_data, create_if_not_exists)
    
    # Extract purchase ID
    purchase_number = purchase_data.get('idkharid')
    if not purchase_number:
        return None, False, "شناسه خرید در داده‌ها یافت نشد"
    
    # Process as a single entry by passing a list with one item to process_grouped_purchase_data
    return process_grouped_purchase_data([purchase_data], create_if_not_exists)


def process_grouped_purchase_data(purchase_data_list, create_if_not_exists=True):
    """
    Process multiple purchase data entries for the same purchase ID (idkharid).
    This handles purchases that have multiple allocation IDs.
    
    Args:
        purchase_data_list (list): List of purchase data dictionaries from the API with the same idkharid
        create_if_not_exists (bool): Whether to create a new purchase if it doesn't exist
        
    Returns:
        tuple: (purchase, created, error_message)
            - purchase: The Purchase object created or updated
            - created: True if a new purchase was created, False otherwise
            - error_message: An error message if the operation failed, None otherwise
            
    Note:
        For purchases with multiple allocation IDs, the purchase state is determined as follows:
        - If the totalweight equals the sum of all wbarnameshode values, the purchase is marked as PURCHASE_CLOSED
        - Otherwise, the state is determined based on standard rules for allocation and barnameh status
    """
    if not purchase_data_list or len(purchase_data_list) == 0:
        return None, False, "لیست داده‌های خرید خالی است"
    
    # Extract purchase ID from the first entry (all entries should have the same ID)
    first_entry = purchase_data_list[0]
    purchase_number = first_entry.get('idkharid')
    if not purchase_number:
        return None, False, "شناسه خرید در داده‌ها یافت نشد"
    
    # Calculate total order weight (sum of 'qty' for all allocation entries)
    # 'qty' is the allocation weight (takhsisweight)
    total_order_weight = sum(int(entry.get('qty', 0) or 0) for entry in purchase_data_list)
    
    # Calculate total delivered weight (sum of 'wbarnameshode' for all entries)
    total_delivered_weight = sum(int(entry.get('wbarnameshode', 0) or 0) for entry in purchase_data_list)
    
    # Print debug information
    logger.debug(f"Debug - Purchase {purchase_number}: {len(purchase_data_list)} allocation records")
    logger.debug(f"Debug - Total order weight (sum of qty): {total_order_weight}")
    logger.debug(f"Debug - Total delivered weight (sum of wbarnameshode): {total_delivered_weight}")
    
    for i, entry in enumerate(purchase_data_list):
        takhsisid = entry.get('allocationid')
        qty = int(entry.get('qty', 0) or 0)
        wbarnameshode = int(entry.get('wbarnameshode', 0) or 0)
        totalweight = int(entry.get('totalweight', 0) or 0)
        logger.debug(f"Debug - Entry {i+1}: allocationid={takhsisid}, qty={qty}, wbarnameshode={wbarnameshode}, totalweight={totalweight}")
    
    try:
        # Search for existing purchase
        purchase = Purchase.objects.get(purchase_number=purchase_number)
        
        # Update the purchase with data from the first entry
        purchase, error = update_purchase(purchase, first_entry)
        if error:
            return None, False, error
        
        # Update with group-level calculated values
        purchase.order_weight = total_order_weight
        purchase.delivered_weight = total_delivered_weight
        
        # Recalculate weight difference
        weight_diff = total_delivered_weight - total_order_weight
        if abs(weight_diff) < 5000 and weight_diff != 0:
            purchase.extelaf_type = "سرک" if weight_diff > 0 else "کسری"
            purchase.extelaf_weight = abs(weight_diff)
            if purchase.customer_price > 0:
                purchase.extelaf_amount = purchase.extelaf_weight * purchase.customer_price
        
        # Update purchase state based on aggregated data - با چک کردن پیشرفت
        # For purchases with multiple allocations, check if totalweight equals total_delivered_weight
        # Get totalweight from the first entry (should be the same for all entries with the same idkharid)
        totalweight = int(first_entry.get('totalweight', 0) or 0)
        
        # تعیین وضعیت پیشنهادی بر اساس داده‌های API
        suggested_state = None
        if totalweight > 0 and totalweight == total_delivered_weight:
            suggested_state = 'PURCHASE_CLOSED'
            logger.debug(f"Debug - API suggests PURCHASE_CLOSED for {purchase_number}: totalweight={totalweight}, total_delivered_weight={total_delivered_weight}")
        else:
            # Check if all entries have allocation IDs
            all_have_allocation = all(
                entry.get('allocationid') and entry.get('allocationid') != '0' 
                for entry in purchase_data_list
            )
            
            if all_have_allocation:
                if total_delivered_weight > 0:
                    if abs(weight_diff) < 5000:
                        suggested_state = 'BARNAMEH_ISSUED'
                    else:
                        suggested_state = 'BARNAMEH_INCOMPLETE'
                else:
                    suggested_state = 'ALLOCATION_APPROVED'
        
        # فقط در صورتی که تغییر وضعیت پیشرفت باشد، آن را اعمال کن
        if suggested_state:
            allowed = can_api_update_state(purchase.state, suggested_state)
            if allowed:
                purchase.state = suggested_state
                log_state_change_attempt(purchase_number, purchase.state, suggested_state, True)
            else:
                reason = ""
                if purchase.state in {'ADDRESS_SENT', 'WAITING_FOR_BARNAMEH', 'PAY_KASRI', 'RECIEIVE_SARAK', 'FULLY_SETTLED', 'INVOICE_ISSUED', 'CANCELED', 'ARCHIVED'}:
                    reason = "(وضعیت فعلی فقط توسط اپراتور قابل تغییر است)"
                elif not is_state_progression(purchase.state, suggested_state):
                    reason = "(تغییر پیشرفت محسوب نمی‌شود)"
                log_state_change_attempt(purchase_number, purchase.state, suggested_state, False, reason)
        else:
            logger.info(f"ℹ️ هیچ تغییر وضعیت برای خرید {purchase_number} پیشنهاد نشد")
        
        # Save changes
        purchase.save()
        
        # Process allocation IDs for all entries
        for entry in purchase_data_list:
            takhsisid = entry.get('allocationid')
            takhsis_weight = int(entry.get('qty', 0) or 0)
            
            if takhsisid and takhsisid != '0':
                # Check if the allocation ID already exists
                if not ShenaseTakhsis.objects.filter(purchase=purchase, code=takhsisid).exists():
                    # Create a new allocation ID
                    ShenaseTakhsis.objects.create(
                        purchase=purchase,
                        code=takhsisid,
                        weight=takhsis_weight
                    )
        
        return purchase, False, None
        
    except Purchase.DoesNotExist:
        if not create_if_not_exists:
            return None, False, f"خرید با شماره {purchase_number} یافت نشد"
        
        # Create a new purchase using the data from the first entry
        purchase, error = create_purchase(first_entry)
        if error:
            return None, False, error
        
        # Update with group-level calculated values
        purchase.order_weight = total_order_weight
        purchase.delivered_weight = total_delivered_weight

        # Check if the purchase should be marked as closed based on the totalweight
        totalweight = int(first_entry.get('totalweight', 0) or 0)
        suggested_state = None
        if totalweight > 0 and totalweight == total_delivered_weight:
            suggested_state = 'PURCHASE_CLOSED'
            logger.debug(f"Debug - API suggests PURCHASE_CLOSED for new purchase {purchase_number}: totalweight={totalweight}, total_delivered_weight={total_delivered_weight}")
        
        # فقط در صورتی که تغییر وضعیت پیشرفت باشد، آن را اعمال کن
        if suggested_state:
            allowed = can_api_update_state(purchase.state, suggested_state)
            if allowed:
                purchase.state = suggested_state
                log_state_change_attempt(purchase_number, purchase.state, suggested_state, True)
            else:
                reason = ""
                if purchase.state in {'ADDRESS_SENT', 'WAITING_FOR_BARNAMEH', 'PAY_KASRI', 'RECIEIVE_SARAK', 'FULLY_SETTLED', 'INVOICE_ISSUED', 'CANCELED', 'ARCHIVED'}:
                    reason = "(وضعیت فعلی فقط توسط اپراتور قابل تغییر است)"
                elif not is_state_progression(purchase.state, suggested_state):
                    reason = "(تغییر پیشرفت محسوب نمی‌شود)"
                log_state_change_attempt(purchase_number, purchase.state, suggested_state, False, reason)
        # Otherwise, the state is already set by create_purchase function

        purchase.save()
        
        # Process additional allocation IDs (the first one was already processed in create_purchase)
        for entry in purchase_data_list[1:]:
            takhsisid = entry.get('allocationid')
            takhsis_weight = int(entry.get('qty', 0) or 0)
            
            if takhsisid and takhsisid != '0':
                # Check if the allocation ID already exists
                if not ShenaseTakhsis.objects.filter(purchase=purchase, code=takhsisid).exists():
                    # Create a new allocation ID
                    ShenaseTakhsis.objects.create(
                        purchase=purchase,
                        code=takhsisid,
                        weight=takhsis_weight
                    )
        
        return purchase, True, None
    
    except Exception as e:
        return None, False, f"خطا در پردازش خرید: {str(e)}"


def group_purchase_data_by_id(purchase_data_list):
    """
    Group purchase data from the BKI API by purchase ID (idkharid).
    
    Args:
        purchase_data_list (list): List of purchase data dictionaries from the API
        
    Returns:
        dict: Dictionary with purchase IDs as keys and lists of purchase data entries as values
    """
    grouped_data = {}
    
    for entry in purchase_data_list:
        purchase_id = entry.get('idkharid')
        if not purchase_id:
            continue
            
        if purchase_id not in grouped_data:
            grouped_data[purchase_id] = []
            
        grouped_data[purchase_id].append(entry)
    
    return grouped_data


def process_purchase_data_batch(purchase_data_list, create_if_not_exists=True):
    """
    Process a batch of purchase data from the BKI API.
    
    Args:
        purchase_data_list (list): List of purchase data dictionaries from the API
        create_if_not_exists (bool): Whether to create new purchases if they don't exist
        
    Returns:
        tuple: (processed_count, created_count, error_count, errors)
            - processed_count: Number of purchases processed
            - created_count: Number of new purchases created
            - error_count: Number of purchases that failed to process
            - errors: Dictionary of error messages with purchase IDs as keys
    """
    processed_count = 0
    created_count = 0
    error_count = 0
    errors = {}
    
    # Group purchase data by purchase ID
    grouped_data = group_purchase_data_by_id(purchase_data_list)
    
    # Process each group
    for purchase_id, entries in grouped_data.items():
        try:
            purchase, created, error = process_purchase_data(entries, create_if_not_exists)
            
            if error:
                error_count += 1
                errors[purchase_id] = error
            else:
                processed_count += 1
                if created:
                    created_count += 1
        except Exception as e:
            error_count += 1
            errors[purchase_id] = str(e)
    
    return processed_count, created_count, error_count, errors 