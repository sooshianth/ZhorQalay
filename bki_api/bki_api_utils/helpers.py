"""
Helper functions for data cleaning and validation
================================================

This module contains utility functions for cleaning and validating data.
"""

import re
from django.utils import timezone
from django_jalali.db import models as jmodels


def clean_phone_number(phone):
    """
    Clean and validate phone numbers to ensure they are in the correct format.
    
    Args:
        phone (str): The input phone number to clean
        
    Returns:
        tuple: (cleaned_number, error_message)
            - cleaned_number: A standardized phone number in the format '9XXXXXXXXX'
            - error_message: An error message if the phone number is invalid, None otherwise
    """
    # If input is empty, return error but don't default to a static number
    if not phone:
        return "", "شماره تلفن خالی است"
        
    # Convert Persian digits to English digits
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    english_digits = "0123456789"
    translation_table = str.maketrans(persian_digits, english_digits)
    phone = str(phone).strip().translate(translation_table)
    
    # Remove non-digit characters
    original_phone = phone
    cleaned_number = ''.join(c for c in phone if c.isdigit())
    
    # If no digits were extracted, return the original number with an error
    if not cleaned_number:
        return original_phone, f"شماره تلفن {phone} فاقد عدد است"
    
    # Handle special case: Check if the number was previously set to 9000000000
    if cleaned_number == "9000000000" and original_phone != "9000000000":
        # This is likely a previously incorrectly stored number, return original
        return original_phone, f"شماره تلفن قبلا به صورت نادرست ذخیره شده بود"
    
    # Remove leading zero if present
    if cleaned_number.startswith('0'):
        cleaned_number = cleaned_number[1:]
    
    # Remove Iran country code if present
    if cleaned_number.startswith('98'):
        cleaned_number = cleaned_number[2:]
    
    # Save original for possible fallback
    final_number = cleaned_number
    
    # Generate warning messages but still return a valid number
    warning = None
    
    # Check if the number is shorter than expected
    if len(cleaned_number) < 10:
        warning = f"شماره {phone} کوتاه تر از حد انتظار است اما حفظ می‌شود"
    # Check if the number is longer than expected but keep it
    elif len(cleaned_number) > 10:
        warning = f"شماره {phone} طولانی تر از حد انتظار است اما حفظ می‌شود"
    
    # Check if the number is a mobile number (starts with 9)
    if not cleaned_number.startswith('9'):
        # Still keep the number, but add a warning
        warning = f"شماره {phone} یک شماره موبایل استاندارد نیست اما حفظ می‌شود"
    
    return final_number, warning


def update_incorrect_phone_numbers(purchase_data):
    """
    Update phone numbers that were previously stored as "9000000000" with correct values from new data.
    
    This function takes purchase data from the BKI API and checks if there are any customers with
    phone numbers set to "9000000000". If found, it updates them with the correct phone numbers
    from the purchase data.
    
    Args:
        purchase_data (dict): Purchase data from the BKI API containing buyer information
        
    Returns:
        tuple: (updated_count, error_count)
            - updated_count: Number of phone numbers updated
            - error_count: Number of errors encountered
    """
    from core.CustomerModel import Customer, PhoneNumber
    
    updated_count = 0
    error_count = 0
    
    try:
        # Get buyer information from purchase data
        buyer_name = purchase_data.get('buyername')
        buyer_phone = purchase_data.get('buyerphone')
        
        if not buyer_name or not buyer_phone:
            return 0, 0  # No buyer information to process
        
        # Clean the phone number
        clean_phone, error = clean_phone_number(buyer_phone)
        if not clean_phone:
            return 0, 1  # Could not clean phone number
        
        # Look for the customer by name
        customers = Customer.objects.filter(name=buyer_name)
        
        for customer in customers:
            # Check if any of the customer's phone numbers is "9000000000"
            incorrect_phones = PhoneNumber.objects.filter(customer=customer, number="9000000000")
            
            for phone in incorrect_phones:
                # Update with the correct phone number
                phone.number = clean_phone
                phone.save()
                updated_count += 1
                print(f"شماره تلفن مشتری {buyer_name} از 9000000000 به {clean_phone} به‌روزرسانی شد")
        
        return updated_count, error_count
    
    except Exception as e:
        print(f"خطا در به‌روزرسانی شماره‌های تلفن نادرست: {str(e)}")
        return updated_count, error_count + 1


def convert_persian_date_to_gregorian(persian_date_str):
    """
    Convert a Persian (Jalali) date string to a Gregorian date object.
    
    Args:
        persian_date_str (str): A date string in Persian calendar format (e.g., '1400/01/01')
        
    Returns:
        datetime.date or None: A Gregorian date object if conversion is successful, None otherwise
    """
    if not persian_date_str:
        return None
    
    try:
        # Convert Persian digits to English digits
        persian_digits = "۰۱۲۳۴۵۶۷۸۹"
        english_digits = "0123456789"
        translation_table = str.maketrans(persian_digits, english_digits)
        persian_date_str = persian_date_str.translate(translation_table)
        
        # Remove non-digit and non-slash characters
        persian_date_str = ''.join(c for c in persian_date_str if c.isdigit() or c == '/')
        
        # Split the date into year, month, and day components
        parts = persian_date_str.split('/')
        if len(parts) != 3:
            return None
            
        jyear = int(parts[0])
        jmonth = int(parts[1])
        jday = int(parts[2])
        
        # Convert from Jalali to Gregorian
        jalali_date = jmodels.jdatetime.date(jyear, jmonth, jday)
        gregorian_date = jalali_date.togregorian()
        
        return gregorian_date
    except Exception as e:
        print(f"خطا در تبدیل تاریخ شمسی به میلادی: {str(e)}")
        return None


def determine_product_type(product_title):
    """
    Determine the product type based on the product title.
    
    Args:
        product_title (str): The name or title of the product
        
    Returns:
        str: The determined product type code
    """
    if not product_title:
        return 'other'
    
    product_title = product_title.lower()
    
    if 'ذرت' in product_title:
        return 'corn'
    elif 'جو' in product_title:
        return 'barley'
    elif 'سویا' in product_title and 'کنجاله' in product_title:
        if 'دانه داخلی' in product_title:
            return 'local_extracted_soy'
        elif 'دانه خارجی' in product_title:
            return 'foreign_extracted_soy'
        else:
            return 'soy_meal'
    elif 'آفتابگردان' in product_title:
        return 'sunflower_meal'
    elif 'کلزا' in product_title:
        return 'rapeseed_meal'
    elif 'پنبه' in product_title:
        return 'cotton_seed'
    elif 'یونجه' in product_title:
        return 'alfalfa'
    elif 'سویا' in product_title and 'دان' in product_title:
        return 'soy_grain'
    else:
        return 'other' 