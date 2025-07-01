"""
Location data handling
=====================

Functions for handling and converting location-related data like province codes.
"""

import os
import xml.etree.ElementTree as ET
import logging

logger = logging.getLogger("bki_api_location")


# Cache for province mappings to avoid repeated file reads
_PROVINCE_MAPPING = None


def load_province_mapping():
    """
    Load the mapping of province codes to province names from an XML file.
    
    This function reads the ostan_list_response.xml file and creates a dictionary
    mapping province codes to their names.
    
    Returns:
        dict: A dictionary mapping province codes (int) to province names (str)
    """
    global _PROVINCE_MAPPING
    
    # Return the cached mapping if it exists
    if _PROVINCE_MAPPING is not None:
        return _PROVINCE_MAPPING
    
    province_mapping = {}
    try:
        # Path to the XML file with province data
        file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                               'Ostan-City-Codes', 'ostan_list_response.xml')
        
        # Check if the file exists
        if not os.path.exists(file_path):
            print(f"خطا: فایل استان‌ها در مسیر {file_path} یافت نشد")
            return {}
            
        # Read and parse the XML file
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # XML namespaces
        namespaces = {
            'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
            'diffgr': 'urn:schemas-microsoft-com:xml-diffgram-v1'
        }
        
        # Extract province data
        for table in root.findall('.//Table1', namespaces):
            code_elem = table.find('bazargahostancode')
            name_elem = table.find('nameostan')
            
            if code_elem is not None and name_elem is not None:
                code = int(code_elem.text)
                name = name_elem.text
                province_mapping[code] = name
        
        # Cache the mapping for future use
        _PROVINCE_MAPPING = province_mapping
        return province_mapping
    except Exception as e:
        print(f"خطا در بارگذاری فایل استان‌ها: {str(e)}")
        return {}


def get_province_name(province_code):
    """
    Convert a province code to its name.
    
    Args:
        province_code (str or int): The code of the province
        
    Returns:
        str or None: The name of the province if the code is valid, None otherwise
    """
    if not province_code:
        return None
    
    try:
        code = int(province_code)
        province_mapping = load_province_mapping()
        return province_mapping.get(code)
    except (ValueError, TypeError):
        return None 