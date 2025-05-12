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
from .helpers import clean_phone_number, determine_product_type
from .location import get_province_name
import jdatetime
from django.utils import timezone


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
        print(f"توجه: {error}")
    
    # Search for the customer by phone number
    customer = None
    created = False
    
    try:
        # Search in phone numbers
        phone = PhoneNumber.objects.filter(number=clean_phone).first()
        if phone:
            customer = phone.customer
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
            print(f"کارشناس فروش مدیریت به مشتری {customer.name} اضافه شد")
            return True
    except Exception as e:
        print(f"خطا در اختصاص کارشناس فروش به مشتری: {str(e)}")
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
                print(f"محصول جدید با کوتاژ {goodtag} و نوع {product_type} ایجاد شد")
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
        qty = int(purchase_data.get('qty', 0) or 0)  # order weight
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
        
        # Determine purchase state
        purchase_state = determine_purchase_state(purchase_data)
        
        # Update purchase fields
        purchase.buyer_name = buyer_name
        purchase.order_weight = qty
        purchase.delivered_weight = wbarnameshode
        purchase.address = buyer_address
        purchase.bazaargah_phone_number = buyer_phone
        purchase.payment_method = payment_type
        purchase.customer_price = fee
        purchase.amount_paid = total_value
        purchase.tahvil_phone_number = receiver_phone
        purchase.tracking_number = trace_code
        purchase.code_melli_tahvil = receiver_id
        
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
                print(f"خطا در تبدیل تاریخ: {str(e)}")
        
        # Update difference fields
        if extelaf_type:
            purchase.extelaf_type = extelaf_type
            purchase.extelaf_weight = extelaf_weight
            if fee > 0:
                purchase.extelaf_amount = extelaf_weight * fee
        
        # Update purchase state
        if purchase_state != purchase.state:
            # Only update if the state is new
            purchase.state = purchase_state
        
        # Save changes
        purchase.save()
        
        # Process allocation ID
        if takhsisid and takhsisid != '0':
            # Check if the allocation ID already exists
            if not ShenaseTakhsis.objects.filter(purchase=purchase, code=takhsisid).exists():
                # Create a new allocation ID
                ShenaseTakhsis.objects.create(
                    purchase=purchase,
                    code=takhsisid,
                    weight=qty
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
        qty = int(purchase_data.get('qty', 0) or 0)  # order weight
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
        
        # Determine purchase state
        purchase_state = determine_purchase_state(purchase_data)
        
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
        
        # تنظیم پارامترهای پایه برای ایجاد خرید
        purchase_params = {
            'purchase_number': purchase_number,
            'customer': customer,
            'cargo': cargo,
            'buyer_name': buyer_name,
            'bazaargah_phone_number': buyer_phone,
            'address': buyer_address,
            'order_weight': qty,
            'delivered_weight': wbarnameshode,
            'customer_price': fee,
            'payment_method': payment_type,
            'type': 'bazaargah',
            'state': purchase_state,
            'extelaf_type': extelaf_type,
            'extelaf_weight': extelaf_weight,
            'extelaf_amount': extelaf_weight * fee if extelaf_weight and fee else 0,
            'amount_paid': total_value,
            'tahvil_phone_number': receiver_phone,
            'tracking_number': trace_code,
            'code_melli_tahvil': receiver_id,
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
                print(f"خطا در تبدیل تاریخ: {str(e)}")
        
        # Create a new purchase
        purchase = Purchase.objects.create(**purchase_params)
        
        # Create allocation ID
        if takhsisid and takhsisid != '0':
            ShenaseTakhsis.objects.create(
                purchase=purchase,
                code=takhsisid,
                weight=qty
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
    qty = int(purchase_data.get('qty', 0) or 0)  # order weight
    wbarnameshode = int(purchase_data.get('wbarnameshode', 0) or 0)  # delivered weight
    wbarnamenashode = int(purchase_data.get('wbarnamenashode', 0) or 0)  # remaining weight
    takhsisid = purchase_data.get('allocationid')  # allocation ID
    
    # Calculate weight difference
    weight_diff = 0
    if wbarnameshode > 0 and qty > 0:
        weight_diff = wbarnameshode - qty
    
    # Default state
    purchase_state = 'PAYMENT_VERIFIED'
    
    if wbarnameshode > 0:
        if abs(weight_diff) < 5000:
            purchase_state = 'BARNAMEH_ISSUED'
        else:
            purchase_state = 'BARNAMEH_INCOMPLETE'
    elif takhsisid and takhsisid != '0':
        purchase_state = 'ALLOCATION_APPROVED'
    
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
    # Extract purchase ID
    purchase_number = purchase_data.get('idkharid')
    if not purchase_number:
        return None, False, "شناسه خرید در داده‌ها یافت نشد"
    
    try:
        # Search for existing purchase
        purchase = Purchase.objects.get(purchase_number=purchase_number)
        
        # Update existing purchase
        purchase, error = update_purchase(purchase, purchase_data)
        if error:
            return None, False, error
        
        return purchase, False, None
        
    except Purchase.DoesNotExist:
        if not create_if_not_exists:
            return None, False, f"خرید با شماره {purchase_number} یافت نشد"
        
        # Create a new purchase
        purchase, error = create_purchase(purchase_data)
        if error:
            return None, False, error
        
        return purchase, True, None 