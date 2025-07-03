"""
BKI API Client
=============

Functions for communicating with the BKI API.
"""

import os
import requests
import xmltodict
import urllib3
from django.conf import settings
from ..models import BKILog
from .data_processing import process_purchase_data, group_purchase_data_by_id, process_grouped_purchase_data
import logging

# Disable SSL warnings for compatibility with the API
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("bki_api_client")

def get_bki_credentials():
    """
    Get BKI API credentials from Django settings.
    
    Returns:
        tuple: (username, password) or (None, None) if credentials are not set
    """
    username = getattr(settings, 'BKI_USERNAME', None)
    password = getattr(settings, 'BKI_PASSWORD', None)
    
    # Validate username and password
    if not username or username.strip() == '':
        logger.warning("خطا: نام کاربری API بازارگاه تنظیم نشده است")
        return None, None
        
    if not password or password.strip() == '':
        logger.warning("خطا: رمز عبور API بازارگاه تنظیم نشده است")
        return None, None
    
    return username, password


def send_soap_request(kharid_id):
    """
    Send a SOAP request to the BKI API and get the response.
    
    Args:
        kharid_id (str): The ID of the purchase to get information for
        
    Returns:
        tuple: (purchase_data, log_entry, error_message)
            - purchase_data: A list of dictionaries with purchase data
            - log_entry: The BKILog object created for this request
            - error_message: An error message if the request failed, None otherwise
    """
    username, password = get_bki_credentials()
    if not username or not password:
        raise ValueError("اطلاعات کاربری API بازارگاه در تنظیمات وجود ندارد")

    # API URL with HTTPS
    url = "https://spsws.bki.ir/spsws.asmx"

    # Create a SOAP 1.1 request
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

    soap_redacted_request = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <getKharidInfo xmlns="http://tempuri.org/">
      <userName>***</userName>
      <pass>***</pass>
      <kharidId>{kharid_id}</kharidId>
    </getKharidInfo>
  </soap:Body>
</soap:Envelope>"""

    # Set request headers
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': 'http://tempuri.org/getKharidInfo',
        'Host': 'spsws.bki.ir'
    }

    # Create a log entry for the request
    log_entry = BKILog(
        request_type='getKharidInfo',
        request_data=soap_redacted_request
    )

    try:
        # Send the request with SSL verification disabled if needed
        response = requests.post(url, data=soap_request, headers=headers, verify=False)
        
        # Save the response in the log
        log_entry.response_data = response.text
        
        if response.status_code != 200:
            log_entry.is_successful = False
            log_entry.error_message = f"خطای HTTP: {response.status_code}"
            log_entry.save()
            logger.error(f"خطای HTTP: {response.status_code} - {response.text}")
            return None, log_entry, f"خطای HTTP: {response.status_code}"
        
        # Parse the XML response
        try:
            response_dict = xmltodict.parse(response.text)
            # Get the result from the response
            soap_body = response_dict['soap:Envelope']['soap:Body']
            result = soap_body['getKharidInfoResponse']['getKharidInfoResult']
            
            if not result or not isinstance(result, dict):
                log_entry.is_successful = False
                log_entry.error_message = "فرمت پاسخ نامعتبر است"
                logger.error(f"فرمت پاسخ نامعتبر است: {response.text}")
                log_entry.save()
                return None, log_entry, "فرمت پاسخ نامعتبر است"
            
            # Check for diffgram data
            if 'diffgr:diffgram' in result:
                diffgram = result['diffgr:diffgram']
                if 'NewDataSet' in diffgram and diffgram['NewDataSet']:
                    if 'Table1' in diffgram['NewDataSet']:
                        table1 = diffgram['NewDataSet']['Table1']
                        # Table1 may be a list or a dictionary
                        if isinstance(table1, list):
                            log_entry.is_successful = True
                            log_entry.save()
                            return table1, log_entry, None
                        else:
                            log_entry.is_successful = True
                            log_entry.save()
                            return [table1], log_entry, None
            
            # If we got here, the expected data was not found
            log_entry.is_successful = False
            log_entry.error_message = "هیچ داده خرید در پاسخ یافت نشد"
            logger.error(f"هیچ داده خرید در پاسخ یافت نشد: {response.text}")
            log_entry.save()
            return None, log_entry, "هیچ داده خرید در پاسخ یافت نشد"
        
        except Exception as e:
            log_entry.is_successful = False
            log_entry.error_message = f"خطا در تجزیه پاسخ: {str(e)}"
            logger.error(f"خطا در تجزیه پاسخ: {str(e)}")
            log_entry.save()
            return None, log_entry, f"خطا در تجزیه پاسخ: {str(e)}"
    
    except Exception as e:
        log_entry.is_successful = False
        log_entry.error_message = f"خطا در ارسال درخواست: {str(e)}"
        logger.error(f"خطا در ارسال درخواست: {str(e)}")
        log_entry.save()
        return None, log_entry, f"خطا در ارسال درخواست: {str(e)}"


def analyze_api_response(response_text):
    """
    Analyze the structure of an API response to identify potential issues.
    
    Args:
        response_text (str): The XML response text to analyze
        
    Returns:
        dict: A dictionary with analysis results
    """
    result = {
        'is_valid': False,
        'error': None,
        'structure': {},
        'data_count': 0
    }
    
    try:
        # Parse XML
        response_dict = xmltodict.parse(response_text)
        result['structure']['has_envelope'] = 'soap:Envelope' in response_dict
        
        if not result['structure']['has_envelope']:
            result['error'] = 'ساختار Envelope در پاسخ یافت نشد'
            return result
        
        # Check for Body
        soap_envelope = response_dict['soap:Envelope']
        result['structure']['has_body'] = 'soap:Body' in soap_envelope
        
        if not result['structure']['has_body']:
            result['error'] = 'ساختار Body در پاسخ یافت نشد'
            return result
        
        # Check for method response
        soap_body = soap_envelope['soap:Body']
        
        # Detect the method type from the response
        response_keys = [k for k in soap_body.keys() if k.endswith('Response')]
        
        if not response_keys:
            result['error'] = 'هیچ پاسخ متدی در Body یافت نشد'
            return result
        
        response_key = response_keys[0]
        result['structure']['response_method'] = response_key
        
        # Check for result
        method_response = soap_body[response_key]
        result_keys = [k for k in method_response.keys() if k.endswith('Result')]
        
        if not result_keys:
            result['error'] = 'هیچ نتیجه‌ای در پاسخ متد یافت نشد'
            return result
        
        result_key = result_keys[0]
        result['structure']['result_key'] = result_key
        
        # Check for diffgram
        api_result = method_response[result_key]
        result['structure']['has_diffgram'] = 'diffgr:diffgram' in api_result
        
        if not result['structure']['has_diffgram']:
            result['error'] = 'ساختار diffgram در نتیجه یافت نشد'
            return result
        
        # Check for NewDataSet
        diffgram = api_result['diffgr:diffgram']
        result['structure']['has_dataset'] = 'NewDataSet' in diffgram
        
        if not result['structure']['has_dataset']:
            result['error'] = 'ساختار NewDataSet در diffgram یافت نشد'
            return result
        
        # Check for Table1
        dataset = diffgram['NewDataSet']
        result['structure']['has_table'] = 'Table1' in dataset
        
        if not result['structure']['has_table']:
            result['error'] = 'ساختار Table1 در NewDataSet یافت نشد'
            return result
        
        # Count data items
        table1 = dataset['Table1']
        
        if isinstance(table1, list):
            result['data_count'] = len(table1)
        else:
            result['data_count'] = 1
        
        # Check data validity
        if result['data_count'] > 0:
            # Check for error message in the data
            if isinstance(table1, list):
                last_item = table1[-1]
            else:
                last_item = table1
            
            if 'ErrorCode' in last_item and 'ErrorMsg' in last_item:
                error_code = last_item['ErrorCode']
                error_msg = last_item['ErrorMsg']
                
                if error_code != '0' and error_msg:
                    result['error'] = f"کد خطا: {error_code}, پیام: {error_msg}"
                    return result
        
        # Response is valid
        result['is_valid'] = True
        return result
        
    except Exception as e:
        result['error'] = f"خطا در تجزیه پاسخ: {str(e)}"
        return result


def test_api_connection():
    """
    Test the connection to the BKI API with a simple SOAP request.
    
    Returns:
        tuple: (is_successful, message)
            - is_successful: True if the connection was successful, False otherwise
            - message: A message indicating the result of the test
    """
    username, password = get_bki_credentials()
    if not username or not password:
        return False, "اطلاعات کاربری API بازارگاه در تنظیمات وجود ندارد"
    
    url = "https://spsws.bki.ir/spsws.asmx"
    soap_request = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <getKharidInfo xmlns="http://tempuri.org/">
      <userName>{username}</userName>
      <pass>{password}</pass>
      <kharidId>123456</kharidId>
    </getKharidInfo>
  </soap:Body>
</soap:Envelope>"""
    
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': 'http://tempuri.org/getKharidInfo',
        'Host': 'spsws.bki.ir'
    }
    
    try:
        response = requests.post(url, data=soap_request, headers=headers, verify=False)
        
        if response.status_code != 200:
            return False, f"خطای HTTP: {response.status_code}"
        
        # Check for errors in the XML response
        response_analysis = analyze_api_response(response.text)
        
        if response_analysis['is_valid']:
            return True, "اتصال به API بازارگاه با موفقیت برقرار شد"
        else:
            return False, f"خطا در پاسخ API: {response_analysis['error']}"
    
    except Exception as e:
        return False, f"خطا در ارسال درخواست: {str(e)}"


def get_all_bazaargah_purchases():
    """
    دریافت همه خریدهای بازارگاه با استفاده از API

    Returns:
        tuple: (total_count, success_count, created_count, updated_count, failed_count, errors)
            - total_count: تعداد کل خریدها
            - success_count: تعداد خریدهایی که با موفقیت پردازش شدند
            - created_count: تعداد خریدهایی که جدید ایجاد شدند
            - updated_count: تعداد خریدهایی که به‌روزرسانی شدند
            - failed_count: تعداد خریدهایی که با خطا مواجه شدند
            - errors: لیست خطاها
    """
    # Get API credentials
    username, password, error = get_bki_credentials()
    if error:
        return 0, 0, 0, 0, 0, [error]
    
    try:
        # Build the API request
        url = "https://spsws.bki.ir/spsws.asmx"
        soap_request = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetKharidList xmlns="http://tempuri.org/">
      <userName>{username}</userName>
      <pass>{password}</pass>
    </GetKharidList>
  </soap:Body>
</soap:Envelope>"""

        soap_redacted_request = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetKharidList xmlns="http://tempuri.org/">
      <userName>***</userName>
      <pass>***</pass>
    </GetKharidList>
  </soap:Body>
</soap:Envelope>"""
        
        # Set request headers
        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': 'http://tempuri.org/GetKharidList',
            'Host': 'spsws.bki.ir'
        }
        
        # Create log entry
        from bki_api.models import BKILog
        log_entry = BKILog(
            request_type='GetKharidList',
            request_data=soap_redacted_request
        )
        
        # Send the request
        response = requests.post(url, data=soap_request, headers=headers, verify=False)
        log_entry.response_data = response.text
        
        if response.status_code != 200:
            error_message = f"خطای HTTP: {response.status_code}"
            log_entry.is_successful = False
            log_entry.error_message = error_message
            log_entry.save()
            logger.error(f"خطا در ارسال درخواست GetKharidList: {error_message}, {response.text}")
            return 0, 0, 0, 0, 0, [error_message]
        
        # Parse the XML response
        try:
            # Analyze the API response to ensure it's valid
            analysis = analyze_api_response(response.text)
            if not analysis['is_valid']:
                log_entry.is_successful = False
                log_entry.error_message = f"خطا در تحلیل پاسخ: {analysis['error']}"
                log_entry.save()
                logger.error(f"خطا در تحلیل پاسخ: {analysis['error']}, {response.text}")
                return 0, 0, 0, 0, 0, [f"خطا در تحلیل پاسخ: {analysis['error']}"]
            
            # Parse the XML response
            import xmltodict
            response_dict = xmltodict.parse(response.text)
            
            # Extract the purchase data from the response
            soap_body = response_dict['soap:Envelope']['soap:Body']
            purchases_data = []
            
            if 'GetKharidListResponse' in soap_body:
                result = soap_body['GetKharidListResponse']['GetKharidListResult']
                if 'diffgr:diffgram' in result:
                    diffgram = result['diffgr:diffgram']
                    if 'NewDataSet' in diffgram and diffgram['NewDataSet']:
                        if 'Table1' in diffgram['NewDataSet']:
                            table1 = diffgram['NewDataSet']['Table1']
                            if isinstance(table1, list):
                                purchases_data = table1
                            else:
                                purchases_data = [table1]
            
            log_entry.is_successful = True
            log_entry.error_message = ''
            log_entry.save()
            
        except Exception as e:
            error_message = f"خطا در تجزیه پاسخ:"
            log_entry.is_successful = False
            log_entry.error_message = error_message
            log_entry.save()
            logger.error(f"خطا در تجزیه پاسخ: {error_message}, {str(e)}")
            return 0, 0, 0, 0, 0, [error_message]
    
    except Exception as e:
        # Log the exception type for debugging but don't expose sensitive data
        safe_error_message = "خطا در ارسال درخواست به API بازارگاه"
        logger.error(f"خطا در ارسال درخواست GetKharidList: {type(e).__name__}")
        return 0, 0, 0, 0, 0, [safe_error_message]
    
    # Check if no purchase data was found
    if not purchases_data:
        return 0, 0, 0, 0, 0, ["هیچ داده خرید در پاسخ یافت نشد"]
    
    #logger.info(f"تعداد خریدهای یافت شده: {len(purchases_data)}")
    
    # Group purchases by purchase ID
    from .data_processing import group_purchase_data_by_id, process_grouped_purchase_data
    
    grouped_data = group_purchase_data_by_id(purchases_data)
    #logger.info(f"خریدها به {len(grouped_data)} گروه تقسیم شدند")
    
    # Process grouped purchase data
    total_count = len(grouped_data)
    success_count = 0
    created_count = 0
    updated_count = 0
    failed_count = 0
    errors = []
    
    # Process each group
    for purchase_id, entries in grouped_data.items():
        try:
            
            # Process the group
            purchase, created, error = process_grouped_purchase_data(entries, create_if_not_exists=True)
            if purchase:
                success_count += 1
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            else:
                failed_count += 1
                if error:
                    errors.append(f"خطا در پردازش خرید {purchase_id}: {error}")
        except Exception as e:
            failed_count += 1
            errors.append(f"خطا در پردازش خرید {purchase_id}: {str(e)}")
    
    logger.info(f"نتیجه نهایی: کل={total_count}, موفق={success_count}, جدید={created_count}, بروزرسانی={updated_count}, خطا={failed_count}")
    return total_count, success_count, created_count, updated_count, failed_count, errors 