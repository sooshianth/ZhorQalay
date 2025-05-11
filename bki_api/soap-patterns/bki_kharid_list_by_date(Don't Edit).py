#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import xml.dom.minidom

# Read credentials from .secret file
with open('.secret', 'r') as f:
    lines = f.readlines()
    username = lines[0].split('=')[1].strip()
    password = lines[1].split('=')[1].strip()

# Sample date values
from_date = "1400/01/01"
to_date = "1404/12/29"

# API endpoint with HTTPS
url = "https://spsws.bki.ir/spsws.asmx"

# Create SOAP 1.1 request body for getKharidListByDate
soap_request = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <getKharidListByDate xmlns="http://tempuri.org/">
      <userName>{username}</userName>
      <pass>{password}</pass>
      <fromDate>{from_date}</fromDate>
      <toDate>{to_date}</toDate>
    </getKharidListByDate>
  </soap:Body>
</soap:Envelope>"""

# Set headers for the request
headers = {
    'Content-Type': 'text/xml; charset=utf-8',
    'SOAPAction': 'http://tempuri.org/getKharidListByDate',
    'Host': 'spsws.bki.ir'
}

def main():
    print("Sending request to Bank Keshavarzi API (getKharidListByDate SOAP 1.1 over HTTPS)...")
    print(f"Username: {username}")
    print(f"Date Range: {from_date} to {to_date}")
    
    try:
        # Send the request with verify=False to bypass SSL certificate verification if needed
        response = requests.post(url, data=soap_request, headers=headers, verify=False)
        
        # Save the raw response
        with open("kharid_list_response.txt", "w", encoding="utf-8") as f:
            f.write(f"Status Code: {response.status_code}\n")
            f.write(f"Headers: {response.headers}\n\n")
            f.write(f"Response Content:\n{response.text}")
        
        print(f"Raw response saved to kharid_list_response.txt")
        
        if response.status_code == 200:
            try:
                # Try to parse and pretty-print the XML response
                xml_response = xml.dom.minidom.parseString(response.text)
                pretty_xml = xml_response.toprettyxml(indent="  ")
                
                # Save the formatted XML response
                with open("kharid_list_response.xml", "w", encoding="utf-8") as f:
                    f.write(pretty_xml)
                
                print(f"API call successful! Response saved to kharid_list_response.xml")
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