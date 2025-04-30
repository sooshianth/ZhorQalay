import os
import requests
import json
import xmltodict
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse
from dotenv import load_dotenv
from .models import BKILog
from django.conf import settings

def update_env_file(key, value):
    """Update a specific key in the .env file."""
    env_path = os.path.join(settings.BASE_DIR, '.env')
    
    # Read the existing .env file
    with open(env_path, 'r') as file:
        lines = file.readlines()
    
    # Update the specified key
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            updated = True
            break
    
    # If the key doesn't exist, add it
    if not updated:
        lines.append(f"{key}={value}\n")
    
    # Write the updated content back to the .env file
    with open(env_path, 'w') as file:
        file.writelines(lines)
    
    # Reload environment variables
    load_dotenv()

def credentials_view(request):
    """View for managing BKI API credentials."""
    # Get current credentials from environment variables
    current_username = os.environ.get('BKI_USERNAME', '')
    current_password = os.environ.get('BKI_PASSWORD', '')
    
    context = {
        'current_username': current_username,
        'current_password': current_password,
    }
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Update .env file with new credentials
        if username:
            update_env_file('BKI_USERNAME', username)
        if password:
            update_env_file('BKI_PASSWORD', password)
        
        messages.success(request, 'تنظیمات BKI با موفقیت به‌روزرسانی شد.')
        return redirect('bki_api:credentials')
    
    return render(request, 'bki_api/credentials_form.html', context)

def test_kharid_info(request):
    """View for testing getKharidInfo API."""
    if request.method != 'POST':
        return redirect('bki_api:credentials')
    
    kharid_id = request.POST.get('kharid_id')
    if not kharid_id:
        messages.error(request, 'لطفاً شناسه خرید را وارد کنید.')
        return redirect('bki_api:credentials')
    
    # Get credentials from environment variables
    username = settings.BKI_USERNAME
    password = settings.BKI_PASSWORD
    
    if not username or not password:
        messages.error(request, 'اطلاعات کاربری BKI تنظیم نشده است.')
        return redirect('bki_api:credentials')
    
    # Prepare SOAP request
    soap_url = "http://spsws.bki.ir/spsws.asmx"
    headers = {
        'Content-Type': 'application/soap+xml; charset=utf-8',
        'SOAPAction': 'http://tempuri.org/getKharidInfo'
    }
    
    soap_request = f"""<?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
        <soap:Body>
            <getKharidInfo xmlns="http://tempuri.org/">
                <userName>{username}</userName>
                <pass>{password}</pass>
                <kharidId>{kharid_id}</kharidId>
            </getKharidInfo>
        </soap:Body>
    </soap:Envelope>"""
    
    context = {
        'kharid_id': kharid_id,
        'success': False
    }
    
    try:
        # Send SOAP request
        response = requests.post(soap_url, data=soap_request, headers=headers)
        
        # Save request/response to BKILog
        log_entry = BKILog(
            request_type='getKharidInfo',
            request_data=soap_request,
            response_data=response.text
        )
        
        # Convert XML response to dictionary
        response_dict = xmltodict.parse(response.text)
        
        # Check if response contains error
        if response.status_code != 200:
            log_entry.is_successful = False
            log_entry.error_message = f"HTTP Error: {response.status_code}"
            log_entry.save()
            
            context['error_message'] = f"خطای HTTP: {response.status_code}"
            context['response_data'] = response.text
            return render(request, 'bki_api/test_result.html', context)
        
        # Try to extract the result data
        try:
            # Parse the SOAP response to get the actual data
            soap_body = response_dict['soap:Envelope']['soap:Body']
            result = soap_body['getKharidInfoResponse']['getKharidInfoResult']
            
            # The actual data may be in a complex structure, extract as needed
            # This is a simplified example - you'll need to adapt based on actual response format
            if isinstance(result, dict) and 'schema' in result:
                # Successfully got data
                log_entry.is_successful = True
                log_entry.save()
                
                context['success'] = True
                context['response_data'] = json.dumps(result, indent=2, ensure_ascii=False)
                
                # Extract and parse useful data if possible
                # This is a placeholder - actual parsing depends on response structure
                try:
                    if '#text' in result:
                        parsed_data = {'message': result['#text']}
                    else:
                        parsed_data = {'status': 'Data received but requires custom parsing'}
                    
                    context['parsed_data'] = parsed_data
                except Exception as e:
                    context['parsed_data'] = {'parsing_error': str(e)}
                
                return render(request, 'bki_api/test_result.html', context)
            else:
                # Got response but no valid data
                error_msg = "پاسخ دریافت شد اما داده‌های معتبری یافت نشد"
                log_entry.is_successful = False
                log_entry.error_message = error_msg
                log_entry.save()
                
                context['error_message'] = error_msg
                context['response_data'] = json.dumps(response_dict, indent=2, ensure_ascii=False)
                return render(request, 'bki_api/test_result.html', context)
                
        except Exception as e:
            # Error parsing response
            log_entry.is_successful = False
            log_entry.error_message = str(e)
            log_entry.save()
            
            context['error_message'] = f"خطا در پردازش پاسخ: {str(e)}"
            context['response_data'] = response.text
            return render(request, 'bki_api/test_result.html', context)
    
    except Exception as e:
        # Error sending request
        error_message = f"خطا در برقراری ارتباط با سرویس: {str(e)}"
        
        # Create log entry for the error
        log_entry = BKILog(
            request_type='getKharidInfo',
            request_data=soap_request,
            is_successful=False,
            error_message=error_message
        )
        log_entry.save()
        
        context['error_message'] = error_message
        return render(request, 'bki_api/test_result.html', context) 