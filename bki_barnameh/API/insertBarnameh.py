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
        
        # Create SOAP request
        soap_request = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <insertBarname xmlns="http://tempuri.org/">
      <userName>{username}</userName>
      <pass>{password}</pass>
      <BarNumber>{barnameh.number}</BarNumber>
      <BarSerial>{barnameh.serial}</BarSerial>
      <ISSUDATE>{issue_date}</ISSUDATE>
      <MerchantDeclaredWeight>{barnameh.tonnage}</MerchantDeclaredWeight>
      <KharidId>{barnameh.purchase_number}</KharidId>
      <takhsisId>{barnameh.shenase_takhsis_code}</takhsisId>
    </insertBarname>
  </soap:Body>
</soap:Envelope>"""
        
        # Create log entry
        log_entry = BKIApiLog(
            barnameh=barnameh,
            request_type='insertBarname',
            request_data=soap_request
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
                response_dict = xmltodict.parse(response.text)
                soap_body = response_dict['soap:Envelope']['soap:Body']
                result = soap_body['insertBarnameResponse']['insertBarnameResult']
                
                # Check if operation was successful
                if result == "1":
                    # Update barnameh status
                    barnameh.is_sent_to_bki = True
                    barnameh.is_sent_to_bki_at = jdatetime.datetime.now()
                    barnameh.status = 'PURCHASE_CLOSED'
                    barnameh.save()
                    
                    log_entry.is_successful = True
                    log_entry.save()
                    
                    return {
                        'success': True,
                        'message': 'بارنامه با موفقیت در بازارگاه ثبت شد.'
                    }
                else:
                    log_entry.is_successful = False
                    log_entry.error_message = f"خطا در ثبت بارنامه: {result}"
                    log_entry.save()
                    
                    return {
                        'success': False,
                        'message': f"خطا در ثبت بارنامه: {result}"
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
