#!/usr/bin/env python
import os
import sys
import django
from django.conf import settings
from django.test.runner import DiscoverRunner

if __name__ == "__main__":
    # تنظیم محیط جنگو
    os.environ['DJANGO_SETTINGS_MODULE'] = 'kunqalay.settings'
    django.setup()
    
    # دریافت نام تست مورد نظر از آرگومان خط فرمان
    if len(sys.argv) > 1:
        test_name = sys.argv[1]
    else:
        print("لطفاً نام تست را وارد کنید. مثال:")
        print("python run_specific_test.py excel_manager.tests.BGEFileProcessingTest.test_process_bge_file_successful")
        sys.exit(1)
    
    # اجرای تست مشخص شده
    runner = DiscoverRunner(verbosity=2)
    failures = runner.run_tests([test_name])
    
    sys.exit(bool(failures)) 