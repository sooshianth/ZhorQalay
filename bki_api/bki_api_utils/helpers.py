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
    # Default number for cases where the input is invalid
    default_number = "9000000000"
    
    if not phone:
        return default_number, "شماره تلفن خالی است"
        
    # Convert Persian digits to English digits
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    english_digits = "0123456789"
    translation_table = str.maketrans(persian_digits, english_digits)
    phone = str(phone).strip().translate(translation_table)
    
    # Remove non-digit characters
    cleaned_number = ''.join(c for c in phone if c.isdigit())
    
    # If no digits were extracted, return the default number
    if not cleaned_number:
        return default_number, f"شماره تلفن {phone} فاقد عدد است"
    
    # Remove leading zero if present
    if cleaned_number.startswith('0'):
        cleaned_number = cleaned_number[1:]
    
    # Remove Iran country code if present
    if cleaned_number.startswith('98'):
        cleaned_number = cleaned_number[2:]
    
    # Check if the number is shorter than expected
    if len(cleaned_number) < 10:
        return default_number, f"شماره {phone} ناقص یا غیرمعتبر است"
    
    # Check if the number is a mobile number (starts with 9)
    if not cleaned_number.startswith('9'):
        return default_number, f"شماره {phone} یک شماره موبایل نیست"
    
    return cleaned_number, None


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