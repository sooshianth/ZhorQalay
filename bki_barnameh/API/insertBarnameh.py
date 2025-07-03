import requests
import xml.dom.minidom
import xmltodict
from django.conf import settings
from ..models.BarnamehModel import Barnameh, BarnamehLog
from ..models.ApiLogModel import BKIApiLog
import jdatetime
from django.utils import timezone
import logging

logger = logging.getLogger('bki_barnameh_insert_barnameh')

def send_barnameh_to_bki(barnameh_id):
    """
    Send Barnameh data to BKI API using SOAP
    
    Args:
        barnameh_id: ID of the Barnameh object to send
    
    Returns:
        dict: Result of the API call
    """
    try:
        barnameh = Barnameh.objects.get(id=barnameh_id)
        
        # Check if barnameh is already sent
        if barnameh.is_sent_to_bki:
            # Create log entry for already sent barnameh
            BarnamehLog.objects.create(
                barnameh=barnameh,
                log_message=f"تلاش مجدد برای ارسال بارنامه به بازارگاه - بارنامه قبلاً ارسال شده است",
                log_date=timezone.now()
            )
            return {
                'success': False,
                'message': 'این بارنامه قبلاً به بازارگاه ارسال شده است.'
            }
        
        # Check if barnameh has all required fields
        if not all([barnameh.number, barnameh.serial, barnameh.tonnage, 
                   barnameh.purchase_number, barnameh.shenase_takhsis_code]):
            # Create log entry for incomplete barnameh
            missing_fields = []
            if not barnameh.number: missing_fields.append('شماره بارنامه')
            if not barnameh.serial: missing_fields.append('سریال بارنامه')
            if not barnameh.tonnage: missing_fields.append('وزن')
            if not barnameh.purchase_number: missing_fields.append('شناسه خرید')
            if not barnameh.shenase_takhsis_code: missing_fields.append('شناسه تخصیص')
            
            BarnamehLog.objects.create(
                barnameh=barnameh,
                log_message=f"تلاش برای ارسال بارنامه ناقص به بازارگاه - فیلدهای ناقص: {', '.join(missing_fields)}",
                log_date=timezone.now()
            )
            return {
                'success': False,
                'message': 'اطلاعات بارنامه ناقص است.'
            }
        
        # Get API credentials from settings
        username = getattr(settings, 'BKI_USERNAME', None)
        password = getattr(settings, 'BKI_PASSWORD', None)
        
        if not username or not password:
            return {
                'success': False,
                'message': 'اطلاعات کاربری API بازارگاه تنظیم نشده است.'
            }
        
        # Format date as string (YYYY/MM/DD)
        issue_date = ""
        if barnameh.barnameh_date:
            issue_date = barnameh.barnameh_date.strftime('%Y/%m/%d')
        
        # Clean and convert purchase_number and shenase_takhsis_code
        try:
            # پاکسازی صحیح اعداد: تبدیل به float و سپس به int برای حذف اعشار
            try:
                if '.' in barnameh.purchase_number:
                    purchase_cleaned = str(int(float(barnameh.purchase_number)))
                else:
                    purchase_cleaned = ''.join(c for c in barnameh.purchase_number if c.isdigit())
                
                if '.' in barnameh.shenase_takhsis_code:
                    takhsis_cleaned = str(int(float(barnameh.shenase_takhsis_code)))
                else:
                    takhsis_cleaned = ''.join(c for c in barnameh.shenase_takhsis_code if c.isdigit())
            except (ValueError, TypeError):
                # اگر تبدیل به float خطا داشت، فقط کاراکترهای عددی را نگه می‌داریم
                purchase_cleaned = ''.join(c for c in barnameh.purchase_number if c.isdigit())
                takhsis_cleaned = ''.join(c for c in barnameh.shenase_takhsis_code if c.isdigit())
            
            if not purchase_cleaned or not takhsis_cleaned:
                return {
                    'success': False,
                    'message': 'شناسه خرید یا شناسه تخصیص فاقد مقدار عددی معتبر است.'
                }
            
            # تبدیل به عدد برای بررسی
            int(purchase_cleaned)
            int(takhsis_cleaned)
            
            # استفاده از مقادیر اصلی برای ارسال
            kharid_id = purchase_cleaned
            takhsis_id = takhsis_cleaned
        except (ValueError, TypeError, AttributeError) as e:
            return {
                'success': False,
                'message': f'خطا در پردازش شناسه خرید یا شناسه تخصیص: {str(e)}'
            }
        
        
        # تبدیل وزن به عدد صحیح (بدون اعشار)
        try:
            if barnameh.tonnage:
                # تبدیل به float و سپس به int برای حذف اعشار
                weight = str(int(float(barnameh.tonnage)))
            else:
                weight = "0"
        except (ValueError, TypeError) as e:
            # اگر مشکلی در تبدیل وجود داشت، سعی می‌کنیم بهترین عملکرد را داشته باشیم
            try:
                weight = str(barnameh.tonnage).split('.')[0]  # حذف کامل اعشار
            except:
                weight = str(barnameh.tonnage)
                logger.info(f"خطا در تبدیل وزن به عدد صحیح، استفاده از مقدار جایگزین: {weight}")
        
        # تبدیل شماره بارنامه و سریال به صورت عدد صحیح (بدون اعشار)
        try:
            # تبدیل شماره بارنامه
            if barnameh.number and '.' in str(barnameh.number):
                # تبدیل به float و سپس به int برای حذف اعشار
                number = str(int(float(barnameh.number)))
            else:
                number = barnameh.number
                
            # سریال بارنامه معمولاً دارای فرمت خاص است (مثل 11/1404)، آن را دست نمی‌زنیم
            serial = barnameh.serial
                
        except (AttributeError, TypeError, ValueError) as e:
            number = barnameh.number
            serial = barnameh.serial
            logger.warning(f"خطا در پردازش شماره یا سریال بارنامه: {str(e)}, شماره بارنامه: {barnameh.number}, سریال بارنامه: {barnameh.serial}")
        
        # XML layout exactly matching the template
        soap_request = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <insertBarname xmlns="http://tempuri.org/">
      <userName>""" + username + """</userName>
      <pass>""" + password + """</pass>
      <BarNumber>""" + number + """</BarNumber>
      <BarSerial>""" + serial + """</BarSerial>
      <ISSUDATE>""" + issue_date + """</ISSUDATE>
      <MerchantDeclaredWeight>""" + weight + """</MerchantDeclaredWeight>
      <KharidId>""" + str(kharid_id) + """</KharidId>
      <takhsisId>""" + str(takhsis_id) + """</takhsisId>
    </insertBarname>
  </soap:Body>
</soap:Envelope>"""

        # XML layout exactly matching the template
        soap_redacted_request = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <insertBarname xmlns="http://tempuri.org/">
      <userName>***</userName>
      <pass>***</pass>
      <BarNumber>""" + number + """</BarNumber>
      <BarSerial>""" + serial + """</BarSerial>
      <ISSUDATE>""" + issue_date + """</ISSUDATE>
      <MerchantDeclaredWeight>""" + weight + """</MerchantDeclaredWeight>
      <KharidId>""" + str(kharid_id) + """</KharidId>
      <takhsisId>""" + str(takhsis_id) + """</takhsisId>
    </insertBarname>
  </soap:Body>
</soap:Envelope>"""        
        
        # Create log entry
        log_entry = BKIApiLog(
            barnameh=barnameh,
            request_type='insertBarname',
            request_data=soap_redacted_request,
            debug_info=f"Original values: purchase_number={barnameh.purchase_number}, shenase_takhsis_code={barnameh.shenase_takhsis_code}, tonnage={barnameh.tonnage}, barnameh_number={barnameh.number}, barnameh_serial={barnameh.serial}\nCleaned values: kharid_id={kharid_id}, takhsis_id={takhsis_id}, weight={weight}, number={number}, serial={serial}\nFull XML:\n{soap_redacted_request}"
        )
        
        # Send request to BKI API
        url = "https://spsws.bki.ir/spsws.asmx"
        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': 'http://tempuri.org/insertBarname',
            'Host': 'spsws.bki.ir'
        }
        
        try:
            response = requests.post(url, data=soap_request, headers=headers, verify=False)
            
            # Save response to log
            log_entry.response_data = response.text
            
            # Add debug info
            log_entry.debug_info += f"\nStatus code: {response.status_code}\nRequest headers: {headers}"
            
            if response.status_code != 200:
                log_entry.is_successful = False
                log_entry.error_message = f"خطای HTTP: {response.status_code}"
                log_entry.save()
                logger.error(f"خطای HTTP: {response.status_code}, {response.text}")
                return {
                    'success': False,
                    'message': f"خطای HTTP: {response.status_code}"
                }
            
            # Parse XML response
            try:
                print(response.text)
                response_dict = xmltodict.parse(response.text)
                soap_body = response_dict['soap:Envelope']['soap:Body']
                result = soap_body['insertBarnameResponse']['insertBarnameResult']
                
                # Log detailed response structure for debugging
                log_entry.debug_info += f"\nResponse structure: {str(response_dict)}"
                
                # Check if operation was successful
                # API can return different response structures in case of success
                is_success = False
                error_message = "خطا در ثبت بارنامه"
                response_xml_info = {}
                
                
                # Try to extract response data and error messages
                try:
                    # First, try to extract any error message that might be directly in the result
                    if isinstance(result, dict):
                        if 'errormsg' in result:
                            error_message = result['errormsg']
                        elif 'ErrorMsg' in result:
                            error_message = result['ErrorMsg']
                    
                    # Extract data from Table1 if it exists in the response structure
                    if isinstance(result, dict):
                        # Check for diffgram format (most common format)
                        if 'diffgr:diffgram' in result and 'NewDataSet' in result['diffgr:diffgram']:
                            if 'Table1' in result['diffgr:diffgram']['NewDataSet']:
                                table1 = result['diffgr:diffgram']['NewDataSet']['Table1']
                                response_xml_info = table1.copy()
                                
                                # Check for error code in this structure
                                if 'errorcode' in table1 and (table1['errorcode'] == '0' or table1['errorcode'] == 0):
                                    is_success = True
                                elif 'ErrorCode' in table1 and (table1['ErrorCode'] == '0' or table1['ErrorCode'] == 0):
                                    is_success = True
                                
                                # Extract error message if present
                                if 'ErrorMsg' in table1:
                                    error_message = table1['ErrorMsg']
                                elif 'errormsg' in table1:
                                    error_message = table1['errormsg']
                        
                        # Check for direct values in result
                        elif 'errorcode' in result and (result['errorcode'] == '0' or result['errorcode'] == 0):
                            is_success = True
                            response_xml_info = result.copy()
                        
                        # Check for NewDataSet format
                        elif 'NewDataSet' in result and 'Table1' in result['NewDataSet']:
                            table1 = result['NewDataSet']['Table1']
                            response_xml_info = table1.copy()
                            
                            if 'ErrorCode' in table1 and (table1['ErrorCode'] == '0' or table1['ErrorCode'] == 0):
                                is_success = True
                            
                            # Extract error message if present
                            if 'ErrorMsg' in table1:
                                error_message = table1['ErrorMsg']
                            elif 'errormsg' in table1:
                                error_message = table1['errormsg']
                except Exception as e:
                    log_entry.debug_info += f"\nError extracting data from response: {str(e)}"
                    logger.error(f"خطا در استخراج داده از پاسخ: {str(e)}")
                
                # Also check for successful string result "1"
                if isinstance(result, str) and result == "1":
                    is_success = True
                
                # Check for error message indicating it's already registered
                already_registered = False
                try:
                    if isinstance(result, dict):
                        error_text = ""
                        if 'errormsg' in result and result['errormsg']:
                            error_text = str(result['errormsg'])
                        elif 'diffgr:diffgram' in result and 'NewDataSet' in result['diffgr:diffgram']:
                            table = result['diffgr:diffgram']['NewDataSet'].get('Table1', {})
                            if 'ErrorMsg' in table:
                                error_text = str(table['ErrorMsg'])
                                
                        # بررسی خطاهای مربوط به ثبت قبلی بارنامه
                        if error_text and ('قبلا ثبت شده' in error_text or 'قبلاً ثبت شده' in error_text or 
                                          'بارنامه ثبت شده است' in error_text or 
                                          'امكان ثبت مجدد وجود ندارد' in error_text):
                            already_registered = True
                            is_success = True  # Treat as success for our purposes
                            log_entry.debug_info += "\nBARNAMEH ALREADY REGISTERED - TREATING AS SUCCESS"
                except Exception as e:
                    log_entry.debug_info += f"\nError checking for 'already registered' status: {str(e)}"
                    logger.error(f"خطا در بررسی ثبت قبلی بارنامه: {str(e)}")
                
                # Save detailed information from response
                log_entry.debug_info += f"\nIs success: {is_success}, Already registered: {already_registered}"
                log_entry.debug_info += f"\nExtracted info: {response_xml_info}"
                
                if is_success:
                    # Update barnameh status
                    barnameh.is_sent_to_bki = True
                    barnameh.is_sent_to_bki_at = timezone.now()
                    barnameh.status = 'PURCHASE_CLOSED'
                    barnameh.bki_response_data = response_xml_info
                    
                    # Extract haml_id if available
                    if isinstance(response_xml_info, dict) and ('hamlid' in response_xml_info or 'HamlId' in response_xml_info):
                        haml_id = response_xml_info.get('hamlid') or response_xml_info.get('HamlId')
                        barnameh.haml_id = haml_id
                    
                    barnameh.save()
                    
                    # Create success log
                    BarnamehLog.objects.create(
                        barnameh=barnameh,
                        log_message=f"بارنامه با موفقیت به بازارگاه ارسال شد. شناسه حمل: {barnameh.haml_id or 'نامشخص'}",
                        log_date=timezone.now()
                    )
                    
                    log_entry.is_successful = True
                    log_entry.save()
                    
                    return {
                        'success': True,
                        'message': 'بارنامه با موفقیت به بازارگاه ارسال شد.',
                        'haml_id': barnameh.haml_id
                    }
                else:
                    # Extract error message
                    error_message = "خطا در ثبت بارنامه"
                    if isinstance(response_xml_info, dict):
                        # Try to get the error message from various possible locations in the response
                        if 'ErrorMsg' in response_xml_info:
                            error_message = response_xml_info['ErrorMsg']
                        elif 'errormsg' in response_xml_info:
                            error_message = response_xml_info['errormsg']
                        elif 'error_message' in response_xml_info:
                            error_message = response_xml_info['error_message']
                    
                    # If we couldn't find the error in response_xml_info, try to find it in the full result
                    if error_message == "خطا در ثبت بارنامه" and isinstance(result, dict):
                        if 'errormsg' in result:
                            error_message = result['errormsg']
                        elif 'ErrorMsg' in result:
                            error_message = result['ErrorMsg']
                        elif 'error_message' in result:
                            error_message = result['error_message']
                        # Check in diffgram structure
                        elif 'diffgr:diffgram' in result and 'NewDataSet' in result['diffgr:diffgram']:
                            if 'Table1' in result['diffgr:diffgram']['NewDataSet']:
                                table1 = result['diffgr:diffgram']['NewDataSet']['Table1']
                                if 'ErrorMsg' in table1:
                                    error_message = table1['ErrorMsg']
                                elif 'errormsg' in table1:
                                    error_message = table1['errormsg']
                    
                    # Add the error code if available
                    error_code = None
                    if isinstance(response_xml_info, dict):
                        error_code = response_xml_info.get('ErrorCode') or response_xml_info.get('errorcode')
                    
                    if error_code:
                        error_message = f"کد خطا: {error_code} - {error_message}"
                    
                    # Create error log with the exact API error message
                    BarnamehLog.objects.create(
                        barnameh=barnameh,
                        log_message=f"خطا در ارسال بارنامه به بازارگاه: {error_message}",
                        log_date=timezone.now()
                    )
                    
                    log_entry.is_successful = False
                    log_entry.error_message = error_message
                    log_entry.save()
                    logger.error(f"خطا در ارسال بارنامه به بازارگاه: {error_message}")
                    
                    return {
                        'success': False,
                        'message': f"خطا در ارسال بارنامه به بازارگاه: {error_message}"
                    }
                
            except Exception as e:
                log_entry.is_successful = False
                log_entry.error_message = f"خطا در تجزیه پاسخ: {str(e)}"
                log_entry.save()
                logger.error(f"خطا در تجزیه پاسخ: {str(e)}")
                
                return {
                    'success': False,
                    'message': f"خطا در تجزیه پاسخ: {str(e)}"
                }
                
        except requests.exceptions.RequestException as e:
            log_entry.is_successful = False
            log_entry.error_message = f"خطا در ارسال درخواست: {str(e)}"
            log_entry.save()
            
            # Create error log
            BarnamehLog.objects.create(
                barnameh=barnameh,
                log_message=f"خطا در ارسال درخواست به بازارگاه: {str(e)}",
                log_date=timezone.now()
            )
            
            return {
                'success': False,
                'message': f"خطا در ارسال درخواست: {str(e)}"
            }
            
    except Barnameh.DoesNotExist:
        return {
            'success': False,
            'message': 'بارنامه مورد نظر یافت نشد.'
        }
    except Exception as e:
        logger.error(f"خطا: {str(e)}")
        return {
            'success': False,
            'message': f"خطا: ",

        }

def send_multiple_barnameh_to_bki(barnameh_ids):
    """
    Send multiple Barnameh objects to BKI API
    
    Args:
        barnameh_ids: List of Barnameh IDs to send
    
    Returns:
        dict: Result of the API calls
    """
    results = {
        'success': 0,
        'failed': 0,
        'messages': [],
        'details': []
    }
    
    for barnameh_id in barnameh_ids:
        try:
            barnameh = Barnameh.objects.get(id=barnameh_id)
            result = send_barnameh_to_bki(barnameh_id)
            
            # Add detailed information
            detail = {
                'id': barnameh_id,
                'number': barnameh.number or "نامشخص",
                'serial': barnameh.serial or "نامشخص",
                'success': result['success'],
                'message': result['message']
            }
            results['details'].append(detail)
            
            if result['success']:
                results['success'] += 1
                # Create a log entry for the bulk operation
                BarnamehLog.objects.create(
                    barnameh=barnameh,
                    log_message=f"بارنامه در عملیات ارسال گروهی با موفقیت به بازارگاه ارسال شد.",
                    log_date=timezone.now()
                )
            else:
                results['failed'] += 1
                # Use the exact error message from the API
                error_message = result['message']
                barnameh_identifier = f"{barnameh.number or '?'}/{barnameh.serial or '?'}"
                results['messages'].append(f"بارنامه {barnameh_identifier}: {error_message}")
                
                # Create a log entry for the bulk operation failure
                BarnamehLog.objects.create(
                    barnameh=barnameh,
                    log_message=f"خطا در ارسال گروهی بارنامه به بازارگاه: {error_message}",
                    log_date=timezone.now()
                )
        except Barnameh.DoesNotExist:
            results['failed'] += 1
            results['messages'].append(f"بارنامه با شناسه {barnameh_id} یافت نشد.")
            logger.error(f"بارنامه با شناسه {barnameh_id} یافت نشد.")
        except Exception as e:
            results['failed'] += 1
            results['messages'].append(f"خطا در ارسال بارنامه {barnameh_id}: {str(e)}")
            
            # Try to log the error if we can find the barnameh
            try:
                barnameh = Barnameh.objects.get(id=barnameh_id)
                BarnamehLog.objects.create(
                    barnameh=barnameh,
                    log_message=f"خطای سیستمی در ارسال گروهی بارنامه: {str(e)}",
                    log_date=timezone.now()
                )
                logger.error(f"خطای سیستمی در ارسال گروهی بارنامه: {str(e)}")
            except:
                pass
    
    return results
