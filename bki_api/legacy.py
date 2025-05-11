"""
BKI API Utilities - Legacy Module
================================

This module is provided for backward compatibility with code that imports
from the old structure. All functionality has been moved to the bki_api_utils
package.
"""

# Print version information for debugging
import requests
import xmltodict
print(f"نسخه کتابخانه requests: {requests.__version__}")
try:
    print(f"نسخه کتابخانه xmltodict: {xmltodict.__version__}")
except AttributeError:
    print("نسخه کتابخانه xmltodict نامشخص است")

# Import all the functions to maintain backward compatibility
from .bki_api_utils.helpers import clean_phone_number, convert_persian_date_to_gregorian, determine_product_type
from .bki_api_utils.location import load_province_mapping, get_province_name
from .bki_api_utils.api_client import (
    get_bki_credentials, send_soap_request, analyze_api_response,
    test_api_connection, get_all_bazaargah_purchases
)
from .bki_api_utils.data_processing import (
    process_purchase_data as process_purchase_data_new,
    process_purchase_data, create_or_get_customer, create_or_get_product,
    update_purchase, create_purchase, determine_purchase_state,
    assign_default_sales_agent
)

# For backward compatibility, ensure both names work
process_purchase_data_new = process_purchase_data

# Load province mapping for immediate use
PROVINCE_MAPPING = load_province_mapping() 