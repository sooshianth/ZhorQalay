import requests
import xml.dom.minidom
import xmltodict
from django.conf import settings
from ..models.BarnamehModel import Barnameh
from ..models.ApiLogModel import BKIApiLog
import jdatetime

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
            return {
                'success': False,
                'message': 'این بارنامه قبلاً به بازارگاه ارسال شده است.'
            }
        
        # Check if barnameh has all required fields
        if not all([barnameh.number, barnameh.serial, barnameh.tonnage, 
                   barnameh.purchase_number, barnameh.shenase_takhsis_code]):
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
        
        # Debug prints
        print("Debug info:")
        print(f"purchase_number (original): {barnameh.purchase_number}")
        print(f"shenase_takhsis_code (original): {barnameh.shenase_takhsis_code}")
        print(f"kharid_id (cleaned): {kharid_id}")
        print(f"takhsis_id (cleaned): {takhsis_id}")
        
        # تبدیل وزن به عدد صحیح (بدون اعشار)
        try:
            if barnameh.tonnage:
                # تبدیل به float و سپس به int برای حذف اعشار
                weight = str(int(float(barnameh.tonnage)))
                print(f"وزن بارنامه (تبدیل شده): {weight}")
            else:
                weight = "0"
                print(f"وزن بارنامه یافت نشد، استفاده از مقدار پیش‌فرض: {weight}")
        except (ValueError, TypeError) as e:
            # اگر مشکلی در تبدیل وجود داشت، سعی می‌کنیم بهترین عملکرد را داشته باشیم
            try:
                weight = str(barnameh.tonnage).split('.')[0]  # حذف کامل اعشار
            except:
                weight = str(barnameh.tonnage)
            print(f"خطا در تبدیل وزن به عدد صحیح، استفاده از مقدار جایگزین: {weight}")
        
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
                
            print(f"شماره بارنامه (تبدیل شده): {number}")
            print(f"سریال بارنامه (اصلی): {serial}")
        except (AttributeError, TypeError, ValueError) as e:
            number = barnameh.number
            serial = barnameh.serial
            print(f"خطا در پردازش شماره یا سریال بارنامه: {str(e)}")
        
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

        print(f"Request XML: {soap_request}")
        
        # Create log entry
        log_entry = BKIApiLog(
            barnameh=barnameh,
            request_type='insertBarname',
            request_data=soap_request,
            debug_info=f"Original values: purchase_number={barnameh.purchase_number}, shenase_takhsis_code={barnameh.shenase_takhsis_code}, tonnage={barnameh.tonnage}, barnameh_number={barnameh.number}, barnameh_serial={barnameh.serial}\nCleaned values: kharid_id={kharid_id}, takhsis_id={takhsis_id}, weight={weight}, number={number}, serial={serial}\nFull XML:\n{soap_request}"
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
                
                # Log the entire response structure for debugging
                print("Full response structure:")
                print(str(response_dict))
                
                # Extract data from Table1 if it exists in the response structure
                try:
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
                except Exception as e:
                    log_entry.debug_info += f"\nError extracting data from response: {str(e)}"
                
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
                
                # Save detailed information from response
                log_entry.debug_info += f"\nIs success: {is_success}, Already registered: {already_registered}"
                log_entry.debug_info += f"\nExtracted info: {response_xml_info}"
                
                if is_success:
                    # Update barnameh status
                    barnameh.is_sent_to_bki = True
                    barnameh.is_sent_to_bki_at = jdatetime.datetime.now()
                    barnameh.status = 'PURCHASE_CLOSED'
                    
                    # Extract and update additional information from API response
                    try:
                        # Store the entire response
                        bki_response_data = response_xml_info
                        
                        # Extract and update specific fields from the response
                        if 'hamlid' in response_xml_info:
                            barnameh.haml_id = response_xml_info['hamlid']
                        
                        # Update driver information if available
                        if 'drivern' in response_xml_info and response_xml_info['drivern'] and (not barnameh.driver_name or already_registered):
                            barnameh.driver_name = response_xml_info['drivern']
                        
                        # Update car/vehicle information if available
                        if 'carn' in response_xml_info and response_xml_info['carn'] and (not barnameh.vehicle_plate or already_registered):
                            barnameh.vehicle_plate = response_xml_info['carn']
                        
                        # Update receiver name if available
                        if 'tahvilname' in response_xml_info and response_xml_info['tahvilname'] and (not barnameh.receiver_name or already_registered):
                            barnameh.receiver_name = response_xml_info['tahvilname']
                            
                        # Update receiver address/destination if available
                        if 'tahviladdress' in response_xml_info and response_xml_info['tahviladdress'] and (not barnameh.destination or already_registered):
                            barnameh.destination = response_xml_info['tahviladdress']
                            
                        # Update receiver phone if available
                        if 'tahvilphone' in response_xml_info and response_xml_info['tahvilphone'] and (not barnameh.driver_phone or already_registered):
                            barnameh.driver_phone = response_xml_info['tahvilphone']
                        
                        # Store complete response data
                        barnameh.bki_response_data = bki_response_data
                        log_entry.debug_info += f"\nUpdated barnameh with API response data successfully"
                    except Exception as e:
                        log_entry.debug_info += f"\nError updating barnameh data from API response: {str(e)}"
                    
                    # Save the updated barnameh
                    barnameh.save()
                    
                    # Mark log entry as successful
                    log_entry.is_successful = True
                    log_entry.save()
                    
                    # Return appropriate message
                    if already_registered:
                        return {
                            'success': True,
                            'message': 'این بارنامه قبلاً در بازارگاه ثبت شده است و اطلاعات آن به‌روز شد.'
                        }
                    else:
                        return {
                            'success': True,
                            'message': 'بارنامه با موفقیت در بازارگاه ثبت شد.'
                        }
                else:
                    log_entry.is_successful = False
                    
                    # بررسی خطای مربوط به بارنامه‌ای که قبلاً ثبت شده است
                    error_text = ""
                    if isinstance(result, dict):
                        if 'errormsg' in result:
                            error_text = str(result['errormsg'])
                        elif 'ErrorMsg' in result:
                            error_text = str(result['ErrorMsg'])
                        elif 'diffgr:diffgram' in result and 'NewDataSet' in result['diffgr:diffgram']:
                            table = result['diffgr:diffgram']['NewDataSet'].get('Table1', {})
                            if 'ErrorMsg' in table:
                                error_text = str(table['ErrorMsg'])
                    elif isinstance(result, str):
                        error_text = result
                    
                    log_entry.debug_info += f"\nError text extracted: {error_text}"
                    
                    # اگر خطای مربوط به ثبت قبلی باشد، وضعیت را به PURCHASE_CLOSED تغییر می‌دهیم
                    if (error_text and 
                        ('این بارنامه در تاریخ' in error_text and 'ثبت گردیده است' in error_text and 'امكان ثبت مجدد وجود ندارد' in error_text)):
                        log_entry.debug_info += "\nDETECTED SPECIFIC ERROR: BARNAMEH ALREADY REGISTERED IN BAZARGAH"
                        log_entry.is_successful = True  # تغییر وضعیت به موفق
                        error_message = "این بارنامه قبلاً در بازارگاه ثبت شده است. سیستم وضعیت را به روز کرد."
                        
                        # تغییر وضعیت بارنامه در سیستم
                        barnameh.is_sent_to_bki = True
                        barnameh.is_sent_to_bki_at = jdatetime.datetime.now()
                        barnameh.status = 'PURCHASE_CLOSED'
                        barnameh.save()
                        
                        log_entry.error_message = error_message
                        log_entry.save()
                        
                        return {
                            'success': True,
                            'message': error_message
                        }
                    else:
                        # Extract error message from the response
                        try:
                            # Try to extract the specific error message from various possible response structures
                            if isinstance(result, dict):
                                if 'errormsg' in result and result['errormsg']:
                                    error_message = f"{error_message}: {result.get('errorcode', '')} - {result['errormsg']}"
                                elif 'diffgr:diffgram' in result:
                                    table = result['diffgr:diffgram']['NewDataSet'].get('Table1', {})
                                    if 'ErrorMsg' in table:
                                        error_message = f"{error_message}: {table.get('ErrorCode', '')} - {table['ErrorMsg']}"
                                elif 'NewDataSet' in result and 'Table1' in result['NewDataSet']:
                                    table = result['NewDataSet']['Table1']
                                    if 'ErrorMsg' in table:
                                        error_message = f"{error_message}: {table.get('ErrorCode', '')} - {table['ErrorMsg']}"
                        except Exception as e:
                            error_message = f"{error_message}: {str(result)}"
                            log_entry.debug_info += f"\nError parsing error message: {str(e)}"
                        
                        log_entry.error_message = error_message
                        log_entry.save()
                        
                        return {
                            'success': False,
                            'message': error_message
                        }
                
            except Exception as e:
                log_entry.is_successful = False
                log_entry.error_message = f"خطا در تجزیه پاسخ: {str(e)}"
                log_entry.save()
                
                return {
                    'success': False,
                    'message': f"خطا در تجزیه پاسخ: {str(e)}"
                }
                
        except Exception as e:
            log_entry.is_successful = False
            log_entry.error_message = f"خطا در ارسال درخواست: {str(e)}"
            log_entry.save()
            
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
        return {
            'success': False,
            'message': f"خطا: {str(e)}"
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
        'messages': []
    }
    
    for barnameh_id in barnameh_ids:
        result = send_barnameh_to_bki(barnameh_id)
        
        if result['success']:
            results['success'] += 1
        else:
            results['failed'] += 1
            results['messages'].append(f"بارنامه {barnameh_id}: {result['message']}")
    
    return results
