#!/usr/bin/env python
"""
Test runner script with coverage reporting
To run all tests: python run_tests.py
To run specific tests: python run_tests.py core/tests/test_customer_model.py
"""

import os
import sys
import subprocess

def run_tests():
    """Run pytest with coverage and generate reports"""
    # Default test paths from pytest.ini
    test_paths = [
        'core',
        'sales',
        'CRM',
        'ERP',
        'whatsapp_api',
        'sms_api',
        'excel_manager',
        'chat'
    ]
    
    # Get specific test path from command line args if provided
    if len(sys.argv) > 1:
        test_paths = sys.argv[1:]
    
    # Construct the pytest command with coverage
    cmd = [
        'pytest',
        '--cov=.',
        '--cov-report=term-missing',
        '--cov-report=html',
        '-v'
    ]
    
    # Add test paths to command
    cmd.extend(test_paths)
    
    # Run the tests
    try:
        subprocess.run(cmd, check=True)
        print("\n✅ Tests completed successfully!\n")
        print("Coverage report available in htmlcov/index.html")
    except subprocess.CalledProcessError:
        print("\n❌ Some tests failed. Please check the output above for details.\n")
        sys.exit(1)

if __name__ == '__main__':
    run_tests() 