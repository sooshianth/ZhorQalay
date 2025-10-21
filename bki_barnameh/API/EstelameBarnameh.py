import requests
import xmltodict
from django.conf import settings
from ..models.BarnamehModel import Barnameh
from ..models.ApiLogModel import BKIApiLog
import jdatetime
import logging

logger = logging.getLogger('bugs')

def estelame_barnameh(barnameh_id, from_date=None, to_date=None):
    """
    Query Barnameh data from BKI API using SOAP
    
    Args:
        barnameh_id: ID of the Barnameh object to query
        from_date: Optional from date for query (format: YYYY/MM/DD)
        to_date: Optional to date for query (format: YYYY/MM/DD)
    
    Returns:
        dict: Result of the API call
    """
    try:
        barnameh = Barnameh.objects.get(id=barnameh_id)
        
        # Get API credentials from settings
        username = getattr(settings, 'BKI_USERNAME', None)
        password = getattr(settings, 'BKI_PASSWORD', None)
        
        if not username or not password:
            return {
                'success': False,
                'message': 'اطلاعات کاربری API بازارگاه تنظیم نشده است.'
            }
        
        # Format date as string (YYYY/MM/DD) if not provided
        if not from_date:
            from_date = ""
            # If barnameh has a date, use one month before that date
            if barnameh.barnameh_date:
                month = barnameh.barnameh_date.month - 1
                year = barnameh.barnameh_date.year
                if month < 1:
                    month = 12
                    year -= 1
                from_date = jdatetime.date(year, month, barnameh.barnameh_date.day).strftime('%Y/%m/%d')
        
        if not to_date:
            to_date = ""
            # If barnameh has a date, use that date
            if barnameh.barnameh_date:
                to_date = barnameh.barnameh_date.strftime('%Y/%m/%d')
        
        # Clean purchase number and shenase_takhsis_code
        try:
            # Clean purchase_number
            if '.' in barnameh.purchase_number:
                kharid_id = str(int(float(barnameh.purchase_number)))
            else:
                kharid_id = ''.join(c for c in barnameh.purchase_number if c.isdigit())
            
            # Clean shenase_takhsis_code
            if '.' in barnameh.shenase_takhsis_code:
                takhsis_id = str(int(float(barnameh.shenase_takhsis_code)))
            else:
                takhsis_id = ''.join(c for c in barnameh.shenase_takhsis_code if c.isdigit())
        except (ValueError, TypeError, AttributeError) as e:
            return {
                'success': False,
                'message': f'خطا در پردازش شناسه خرید یا شناسه تخصیص: {str(e)}'
            }
        
        # Create SOAP request
        soap_request = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <EstelameBarname xmlns="http://tempuri.org/">
      <userName>{username}</userName>
      <pass>{password}</pass>
      <fromDate>{from_date}</fromDate>
      <toDate>{to_date}</toDate>
      <kharidId>{kharid_id}</kharidId>
      <TakhsisId>{takhsis_id}</TakhsisId>
      <KutajNumber></KutajNumber>
      <IdHaml></IdHaml>
    </EstelameBarname>
  </soap:Body>
</soap:Envelope>"""

        # Create SOAP request
        soap_redacted_request = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <EstelameBarname xmlns="http://tempuri.org/">
      <userName>***</userName>
      <pass>***</pass>
      <fromDate>{from_date}</fromDate>
      <toDate>{to_date}</toDate>
      <kharidId>{kharid_id}</kharidId>
      <TakhsisId>{takhsis_id}</TakhsisId>
      <KutajNumber></KutajNumber>
      <IdHaml></IdHaml>
    </EstelameBarname>
  </soap:Body>
</soap:Envelope>"""
        
        # Create log entry
        log_entry = BKIApiLog(
            barnameh=barnameh,
            request_type='EstelameBarname',
            request_data=soap_redacted_request
        )
        
        # Send request to BKI API
        url = "https://spsws.bki.ir/spsws.asmx"
        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': 'http://tempuri.org/EstelameBarname',
            'Host': 'spsws.bki.ir'
        }
        
        try:
            response = requests.post(url, data=soap_request, headers=headers, verify=False)
            
            # Save response to log
            log_entry.response_data = response.text
            
            if response.status_code != 200:
                log_entry.is_successful = False
                log_entry.error_message = f"خطای HTTP: {response.status_code}, {response.text}"
                log_entry.save()
                logger.error(f"HTTP error for barnameh {barnameh.id}: {response.status_code}, {response.text}")
                return {
                    'success': False,
                    'message': f"خطای HTTP: {response.status_code}"
                }
            
            # Parse XML response
            try:
                response_dict = xmltodict.parse(response.text)
                soap_body = response_dict['soap:Envelope']['soap:Body']
                result = soap_body['EstelameBarnameResponse']['EstelameBarnameResult']
                
                # Extract barnameh data
                barnameh_data = []
                
                if isinstance(result, dict):
                    if 'diffgr:diffgram' in result and 'NewDataSet' in result['diffgr:diffgram']:
                        if 'Table' in result['diffgr:diffgram']['NewDataSet']:
                            tables = result['diffgr:diffgram']['NewDataSet']['Table']
                            # Handle both single record and multiple records
                            if isinstance(tables, list):
                                barnameh_data = tables
                            else:
                                barnameh_data = [tables]
                            
                            log_entry.is_successful = True
                            log_entry.save()
                            
                            return {
                                'success': True,
                                'message': 'اطلاعات بارنامه با موفقیت دریافت شد.',
                                'data': barnameh_data
                            }
                
                # If we got here, no valid data was found
                log_entry.is_successful = False
                log_entry.error_message = "داده‌ای در پاسخ یافت نشد."
                log_entry.save()
                logger.error(f"Error: No data found in response for barnameh {barnameh.id}")
                
                return {
                    'success': False,
                    'message': "داده‌ای برای این بارنامه در بازارگاه یافت نشد."
                }
                
            except Exception as e:
                log_entry.is_successful = False
                log_entry.error_message = f"خطا در تجزیه پاسخ: {str(e)}"
                log_entry.save()
                logger.error(f"Error parsing response for barnameh {barnameh.id}: {str(e)}")
                return {
                    'success': False,
                    'message': f"خطا در تجزیه پاسخ: {str(e)}"
                }
                
        except Exception as e:
            log_entry.is_successful = False
            log_entry.error_message = f"خطا در ارسال درخواست: {str(e)}"
            log_entry.save()
            logger.error(f"Error sending request for barnameh {barnameh.id}: {str(e)}")

            return {
                'success': False,
                'message': f"خطا در ارسال درخواست: "
            }
            
    except Barnameh.DoesNotExist:
        return {
            'success': False,
            'message': 'بارنامه مورد نظر یافت نشد.'
        }
    except Exception as e:
        logger.error(f"Error in estelame barnameh {barnameh.id}: {str(e)}")
        return {
            'success': False,
            'message': f"خطا: ",
        }
