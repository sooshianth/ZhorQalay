#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import xml.dom.minidom
from django.conf import settings

# Get credentials from Django settings
username = getattr(settings, 'BKI_USERNAME', '')
password = getattr(settings, 'BKI_PASSWORD', '')
example_kharid_id = getattr(settings, 'BKI_EXAMPLE_KHARID_ID', '2310939')

# API endpoint with HTTPS
url = "https://spsws.bki.ir/spsws.asmx"

# Create SOAP 1.1 request body exactly as shown in the example
soap_request = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <getKharidInfo xmlns="http://tempuri.org/">
      <userName>{username}</userName>
      <pass>{password}</pass>
      <kharidId>{example_kharid_id}</kharidId>
    </getKharidInfo>
  </soap:Body>
</soap:Envelope>"""

# Set headers exactly as shown in the example
headers = {
    'Content-Type': 'text/xml; charset=utf-8',
    'SOAPAction': 'http://tempuri.org/getKharidInfo',
    'Host': 'spsws.bki.ir'
}

def main():
    print("Sending request to Bank Keshavarzi API (SOAP 1.1 over HTTPS)...")
    print(f"Username: {username}")
    print(f"KharidID: {example_kharid_id}")
    
    try:
        # Send the request with verify=False to bypass SSL certificate verification if needed
        response = requests.post(url, data=soap_request, headers=headers, verify=False)
        
        # Save the raw response
        with open("soap11_https_response.txt", "w", encoding="utf-8") as f:
            f.write(f"Status Code: {response.status_code}\n")
            f.write(f"Headers: {response.headers}\n\n")
            f.write(f"Response Content:\n{response.text}")
        
        print(f"Raw response saved to soap11_https_response.txt")
        
        if response.status_code == 200:
            try:
                # Try to parse and pretty-print the XML response
                xml_response = xml.dom.minidom.parseString(response.text)
                pretty_xml = xml_response.toprettyxml(indent="  ")
                
                # Save the formatted XML response
                with open("soap11_https_response.xml", "w", encoding="utf-8") as f:
                    f.write(pretty_xml)
                
                print(f"API call successful! Response saved to soap11_https_response.xml")
                return True
            except Exception as e:
                print(f"Warning: Could not parse response as XML: {str(e)}")
                return False
        else:
            print(f"API call failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return False

if __name__ == "__main__":
    main() 