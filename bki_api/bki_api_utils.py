#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import requests
import xml.dom.minidom
import xmltodict
from django.conf import settings
from django.utils import timezone
from datetime import datetime
from core.PurchaseModel import Purchase
from core.CustomerModel import Customer, PhoneNumber
from core.CargoProductModel import CargoProduct
from .models import BKILog

def get_bki_credentials():
    """
    Get BKI API credentials from Django settings
    """
    username = getattr(settings, 'BKI_USERNAME', None)
    password = getattr(settings, 'BKI_PASSWORD', None)
    return username, password

def send_soap_request(kharid_id):
    """
    Send SOAP request to BKI API and return the response
    """
    username, password = get_bki_credentials()
    if not username or not password:
        raise ValueError("BKI API credentials are not configured in settings")

    # API endpoint with HTTPS
    url = "https://spsws.bki.ir/spsws.asmx"

    # Create SOAP 1.1 request body 
    soap_request = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <getKharidInfo xmlns="http://tempuri.org/">
      <userName>{username}</userName>
      <pass>{password}</pass>
      <kharidId>{kharid_id}</kharidId>
    </getKharidInfo>
  </soap:Body>
</soap:Envelope>"""

    # Set headers for the request
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': 'http://tempuri.org/getKharidInfo',
        'Host': 'spsws.bki.ir'
    }

    # Create log entry for the request
    log_entry = BKILog(
        request_type='getKharidInfo',
        request_data=soap_request
    )

    try:
        # Send the request with verify=False to bypass SSL certificate verification if needed
        response = requests.post(url, data=soap_request, headers=headers, verify=False)
        
        # Save response to log
        log_entry.response_data = response.text
        
        if response.status_code != 200:
            log_entry.is_successful = False
            log_entry.error_message = f"HTTP Error: {response.status_code}"
            log_entry.save()
            return None, log_entry, f"HTTP Error: {response.status_code}"
        
        # Parse the XML response
        try:
            response_dict = xmltodict.parse(response.text)
            # Get the result from the response
            soap_body = response_dict['soap:Envelope']['soap:Body']
            result = soap_body['getKharidInfoResponse']['getKharidInfoResult']
            
            if not result or not isinstance(result, dict):
                log_entry.is_successful = False
                log_entry.error_message = "Invalid response format"
                log_entry.save()
                return None, log_entry, "Invalid response format"
            
            # Check for diffgram data
            if 'diffgr:diffgram' in result:
                diffgram = result['diffgr:diffgram']
                if 'NewDataSet' in diffgram and diffgram['NewDataSet']:
                    if 'Table1' in diffgram['NewDataSet']:
                        table1 = diffgram['NewDataSet']['Table1']
                        # Table1 might be a list or a single dictionary
                        if isinstance(table1, list):
                            log_entry.is_successful = True
                            log_entry.save()
                            return table1, log_entry, None
                        else:
                            log_entry.is_successful = True
                            log_entry.save()
                            return [table1], log_entry, None
            
            # If we got here, we didn't find expected data
            log_entry.is_successful = False
            log_entry.error_message = "No purchase data found in response"
            log_entry.save()
            return None, log_entry, "No purchase data found in response"
        
        except Exception as e:
            log_entry.is_successful = False
            log_entry.error_message = f"Error parsing response: {str(e)}"
            log_entry.save()
            return None, log_entry, f"Error parsing response: {str(e)}"
    
    except Exception as e:
        log_entry.is_successful = False
        log_entry.error_message = f"Error sending request: {str(e)}"
        log_entry.save()
        return None, log_entry, f"Error sending request: {str(e)}"

def determine_product_type(product_title):
    """
    Determine product type based on title
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

def process_purchase_data(purchase_data, create_if_not_exists=True):
    """
    Process purchase data and update or create purchase record
    Returns (purchase, created, error_message)
    """
    # Map XML fields to database fields
    field_mappings = {
        'kharididentity': 'purchase_number',
        'kutajnumber': 'cargo__cottage',
        'goodtitle': 'cargo__product_type',
        'weight': 'delivered_weight',
        'buydate': 'created_at',
        'rrn': 'tracking_number',
        'byername': 'customer__name',
        'buyeraddress': 'address',
        'delphone': 'tahvil_phone_number',
        'totalamount': 'amount_paid',
        'paymenttype': 'payment_method',
        'fi': 'customer_price',
        'buyermobile': 'customer__phone_number',
        'buyermellicode': 'code_melli_tahvil',
        'ostanname': 'customer__city',
        'cityname': 'customer__city_detail',
    }
    
    # Extract values from purchase_data
    data = {}
    for xml_field, db_field in field_mappings.items():
        if xml_field in purchase_data:
            data[db_field] = purchase_data[xml_field]
    
    # Check if purchase_number is present
    purchase_number = data.get('purchase_number')
    if not purchase_number:
        return None, False, "Purchase number not found in response"
    
    try:
        # Try to find existing purchase
        purchase = Purchase.objects.get(purchase_number=purchase_number)
        created = False
        
        # Update simple fields
        simple_fields = [
            'delivered_weight', 'tracking_number', 'address', 
            'tahvil_phone_number', 'amount_paid', 'payment_method', 
            'customer_price', 'code_melli_tahvil'
        ]
        
        for field in simple_fields:
            if field in data and data[field]:
                setattr(purchase, field, data[field])
        
        # Update customer fields
        if purchase.customer:
            if 'customer__name' in data and data['customer__name']:
                purchase.customer.name = data['customer__name']
            
            if 'customer__city' in data and data['customer__city']:
                purchase.customer.city = data['customer__city']
            
            if 'customer__phone_number' in data and data['customer__phone_number']:
                primary_phone = purchase.customer.get_primary_phone()
                new_phone = data['customer__phone_number']
                
                if primary_phone != new_phone:
                    # Update primary phone
                    phone = purchase.customer.phone_numbers.filter(is_primary=True).first()
                    if phone:
                        phone.number = new_phone
                        phone.save()
                    else:
                        # Create new phone number
                        PhoneNumber.objects.create(
                            customer=purchase.customer,
                            number=new_phone,
                            is_primary=True
                        )
            
            # Save customer changes
            purchase.customer.save()
        
        # Update dates if needed
        if 'created_at' in data and data['created_at']:
            try:
                # Handle Persian date format (1404/01/24)
                parts = data['created_at'].split('/')
                if len(parts) == 3:
                    # Convert Persian year to Gregorian (very simplified)
                    persian_year = int(parts[0])
                    persian_month = int(parts[1])
                    persian_day = int(parts[2])
                    
                    # Simple conversion: Persian to Gregorian
                    gregorian_year = persian_year - 621
                    
                    # This is a simplification, proper conversion needs a calendar library
                    # For accurate conversion, use jdatetime or similar library
                    gregorian_date = datetime(gregorian_year, persian_month, persian_day)
                    purchase.created_at = timezone.make_aware(gregorian_date)
            except (ValueError, TypeError):
                pass  # Use default date if conversion fails
        
        # Update purchase
        purchase.updated_at = timezone.now()
        purchase.save()
        
        return purchase, created, None
    
    except Purchase.DoesNotExist:
        if not create_if_not_exists:
            return None, False, f"Purchase with number {purchase_number} not found"
        
        # Create new purchase
        try:
            # 1. Find or create customer
            mobile_number = data.get('customer__phone_number')
            if not mobile_number:
                return None, False, "Customer mobile number not found in response"
            
            customer = Customer.get_customer_by_phone(mobile_number)
            customer_existed = customer is not None
            
            if not customer:
                # Create new customer
                customer = Customer.objects.create(
                    name=data.get('customer__name', 'Unknown Customer'),
                    city=data.get('customer__city'),
                )
                
                # Create phone number for customer
                PhoneNumber.objects.create(
                    customer=customer,
                    number=mobile_number,
                    is_primary=True
                )
            
            # 2. Find or create cargo product
            cottage_number = data.get('cargo__cottage')
            cargo = None
            cargo_existed = False
            
            if cottage_number:
                try:
                    cargo = CargoProduct.objects.get(cottage=cottage_number)
                    cargo_existed = True
                except CargoProduct.DoesNotExist:
                    # Create new cargo
                    product_type = 'other'
                    if 'cargo__product_type' in data:
                        product_type = determine_product_type(data['cargo__product_type'])
                    
                    cargo = CargoProduct.objects.create(
                        type='bazaargah',
                        cottage=cottage_number,
                        company_price=data.get('customer_price', 0),
                        customer_price=data.get('customer_price', 0),
                        product_type=product_type,
                        country='iran',  # Default
                        port='امام خمینی',  # Default
                        weight=1000000  # Default: 1000 tons
                    )
            
            # 3. Create new purchase
            new_purchase = Purchase.objects.create(
                purchase_number=purchase_number,
                customer=customer,
                cargo=cargo,
                address=data.get('address'),
                delivered_weight=data.get('delivered_weight', 0),
                tracking_number=data.get('tracking_number'),
                tahvil_phone_number=data.get('tahvil_phone_number'),
                amount_paid=data.get('amount_paid', 0),
                payment_method=data.get('payment_method', 'نقدی'),
                customer_price=data.get('customer_price', 0),
                company_price=data.get('customer_price', 0),
                code_melli_tahvil=data.get('code_melli_tahvil'),
                type='bazaargah',
                state='PAYMENT_VERIFIED'
            )
            
            # Add flags to track if objects existed (for reporting)
            new_purchase._customer_existed = customer_existed
            new_purchase._cargo_existed = cargo_existed
            
            # Set creation date if available
            if 'created_at' in data and data['created_at']:
                try:
                    # Handle Persian date format (1404/01/24)
                    parts = data['created_at'].split('/')
                    if len(parts) == 3:
                        # Convert Persian year to Gregorian (very simplified)
                        persian_year = int(parts[0])
                        persian_month = int(parts[1])
                        persian_day = int(parts[2])
                        
                        # Simple conversion: Persian to Gregorian
                        gregorian_year = persian_year - 621
                        
                        # This is a simplification, proper conversion needs a calendar library
                        gregorian_date = datetime(gregorian_year, persian_month, persian_day)
                        new_purchase.created_at = timezone.make_aware(gregorian_date)
                        new_purchase.save(update_fields=['created_at'])
                except (ValueError, TypeError):
                    pass  # Use default date if conversion fails
            
            return new_purchase, True, None
        
        except Exception as e:
            return None, False, f"Error creating purchase: {str(e)}"

def get_purchase_info(kharid_id, create_if_not_exists=True):
    """
    Get purchase information from BKI API and update or create in database
    """
    # Send SOAP request
    purchases_data, log_entry, error = send_soap_request(kharid_id)
    if error:
        return None, False, error
    
    results = []
    for purchase_data in purchases_data:
        purchase, created, error = process_purchase_data(purchase_data, create_if_not_exists)
        if purchase:
            # Update log entry with purchase reference
            if log_entry and not log_entry.purchase:
                log_entry.purchase = purchase
                log_entry.save()
                
            results.append({
                'purchase': purchase,
                'created': created,
                'error': error
            })
        elif error:
            results.append({
                'purchase': None,
                'created': False,
                'error': error
            })
    
    # Return the first result or None if no results
    if results:
        return results[0]['purchase'], results[0]['created'], results[0]['error']
    return None, False, "No purchases found in API response"

def bulk_update_purchase_info(kharid_ids):
    """
    Update multiple purchases from BKI API
    """
    if isinstance(kharid_ids, str):
        # Split string of IDs by commas, spaces, or newlines
        import re
        kharid_ids = re.split(r'[,\s]+', kharid_ids)
    
    # Filter out empty strings
    kharid_ids = [kid.strip() for kid in kharid_ids if kid.strip()]
    
    results = []
    for kharid_id in kharid_ids:
        try:
            purchase, created, error = get_purchase_info(kharid_id)
            
            if purchase:
                result = {
                    'kharid_id': kharid_id,
                    'success': True,
                    'created': created,
                    'is_new': created,  # Template expects is_new instead of created
                    'purchase': purchase
                }
                
                if created:
                    # For new purchases, provide created objects info
                    result['message'] = f'خرید جدید با شماره {purchase.purchase_number} با موفقیت ایجاد شد'
                    result['created_objects'] = {
                        'customer': {
                            'status': 'found' if hasattr(purchase, '_customer_existed') and purchase._customer_existed else 'created',
                            'id': purchase.customer.id
                        },
                        'cargo': {
                            'status': 'found' if hasattr(purchase, '_cargo_existed') and purchase._cargo_existed else 'created' if purchase.cargo else 'not_created',
                            'id': purchase.cargo.id if purchase.cargo else None,
                            'reason': 'cottage_number_missing' if not purchase.cargo else None
                        },
                        'purchase': {
                            'status': 'created',
                            'id': purchase.id
                        }
                    }
                else:
                    # For existing purchases, provide update info
                    result['message'] = f'اطلاعات خرید {purchase.purchase_number} با موفقیت به‌روزرسانی شد'
                    
                    # These fields are set by update_purchase_info but we need to provide them
                    # since we're bypassing that function - use empty arrays for now
                    result['purchase_updates'] = []
                    result['customer_updates'] = {}
            else:
                # Error case
                result = {
                    'kharid_id': kharid_id,
                    'success': False,
                    'error': error or 'خطای نامشخص در دریافت اطلاعات خرید'
                }
            
            results.append(result)
        except Exception as e:
            results.append({
                'kharid_id': kharid_id,
                'success': False,
                'error': str(e)
            })
    
    return results 