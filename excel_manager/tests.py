from django.test import TestCase, RequestFactory, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from .models import BGExcelFile, ExcelProcessingLog
from core._models import CargoProduct, Purchase
from core.CustomerModel import Customer
from .views.bge_file_views import process_bge_file
import os
import tempfile
import pandas as pd
import shutil
from unittest.mock import patch
import io


class BGEFileProcessingTest(TestCase):
    """
    تست پردازش فایل اکسل بازارگاه
    """
    
    def setUp(self):
        """
        راه‌اندازی داده‌های تست
        """
        # ایجاد یک کاربر تست
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword',
            is_superuser=True
        )
        
        # ایجاد محصول تست
        self.cargo_product = CargoProduct.objects.create(
            cottage='35408055',
            product_type='corn',
            country='brazil',
            port='جنوب',
            loading_time='فوری',
            weight=100000,
            company_price=95000,
            customer_price=100000,
            type='bazaargah'
        )
        
        # ایجاد مسیر موقت برای فایل‌های رسانه
        settings.MEDIA_ROOT = tempfile.mkdtemp()
        
        # ساخت محتوای HTML برای فایل اکسل
        self.sample_html_content = """<html><head><meta http-equiv=Content-Type content='text/html; charset=utf-8'><style> .text { mso-number-format:\@; } .trFormat{color:Black;background-color:#DEDFDE;}</style></head><div style="direction:rtl;padding:5px 0"><span style="font:bold 12px tahoma; color:#008B00;line-height:180%"> ثبت اطلاعات حمل</span></div><table dir='rtl' border='1' cellspacing='0' cellpadding='7' style='font-family:Tahoma;font-size:11px;width:70%;'><tbody><tr style='color:#E7E7FF;background-color:#4A3C8C;font-weight:bold;'><th>کد</th><th>وزن کل خرید</th><th>تاریخ خرید</th><th>قیمت هر واحد</th><th>شماره پیگیری</th><th>استان</th><th>شهرستان</th><th>مبلغ پرداختی</th><th>شماره حساب خریدار</th><th>کد کوتاژ</th><th>شناسه تخصیص</th><th>نام خریدار</th><th>شماره همراه خریدار</th><th>آدرس تحویل</th><th>کد ملی تحویل</th><th>شماره هماهنگی تحویل</th><th>شیوه پرداخت</th></tr><tr class='trFormat'><td align="center">2148123</td><td align="center">14994</td><td align="center">1403/11/07</td><td align="center">95000</td><td align="center">452213</td><td align="center">11</td><td align="center">210</td><td align="center">1424430000</td><td align="center">315384047</td><td align="center">35408055</td><td align="center">1997411</td><td align="center">محمد تستی</td><td align="center">09132017353</td><td align="center">اصفهان، خیابان تست، پلاک 1</td><td align="center">1282915053</td><td align="center">09132017353</td><td align="center">نقدی</td></tr></tbody></table></html>"""
        
        # ایجاد فایل اکسل تست
        with open(os.path.join(settings.MEDIA_ROOT, 'test_excel.xls'), 'w', encoding='utf-8') as f:
            f.write(self.sample_html_content)
            
        self.test_file = SimpleUploadedFile(
            name="test_excel.xls",
            content=self.sample_html_content.encode('utf-8'),
            content_type="application/vnd.ms-excel"
        )
        
        # ایجاد رکورد فایل در دیتابیس
        self.bge_file = BGExcelFile.objects.create(
            user=self.user,
            title='فایل تست',
            file=self.test_file,
            description='توضیحات تست',
            cargo=self.cargo_product
        )
        
        # ساخت یک کلاینت تست
        self.client = Client()
        self.client.login(username='testuser', password='testpassword')
        
        # ساخت یک factory برای ساخت درخواست‌ها
        self.factory = RequestFactory()
        
    def tearDown(self):
        """
        پاکسازی بعد از اتمام تست‌ها
        """
        # حذف دایرکتوری موقت
        shutil.rmtree(settings.MEDIA_ROOT)
    
    @patch('excel_manager.views.bge_file_views.pd.read_html')
    def test_process_bge_file_successful(self, mock_read_html):
        """
        تست پردازش موفق فایل بازارگاه
        """
        # ساختن دیتافریم تست
        df = pd.DataFrame({
            'کد': ['2148123'],
            'وزن کل خرید': [14994],
            'مبلغ پرداختی': [1424430000],
            'کد کوتاژ': ['35408055'],
            'شناسه تخصیص': ['1997411'],
            'نام خریدار': ['محمد تستی'],
            'شماره همراه خریدار': ['09132017353'],
            'آدرس تحویل': ['اصفهان، خیابان تست، پلاک 1'],
            'کد ملی تحویل': ['1282915053'],
            'شماره هماهنگی تحویل': ['09132017353'],
            'شیوه پرداخت': ['نقدی']
        })
        mock_read_html.return_value = [df]
        
        # ساخت درخواست POST
        request = self.factory.post(
            reverse('excel_manager:process_bge_file', args=[self.bge_file.id])
        )
        request.user = self.user
        
        # فراخوانی تابع process_bge_file
        response = process_bge_file(request, self.bge_file.id)
        
        # بررسی نتایج
        self.assertEqual(response.status_code, 302)  # تغییر مسیر بعد از موفقیت
        
        # بررسی به‌روزرسانی وضعیت فایل
        self.bge_file.refresh_from_db()
        self.assertTrue(self.bge_file.is_processed)
        
        # بررسی ایجاد مشتری جدید
        customer = Customer.objects.filter(phone_number='9132017353').first()
        self.assertIsNotNone(customer)
        self.assertEqual(customer.name, 'محمد تستی')
        
        # بررسی ایجاد خرید جدید
        purchase = Purchase.objects.filter(purchase_number='2148123').first()
        self.assertIsNotNone(purchase)
        self.assertEqual(purchase.customer, customer)
        self.assertEqual(purchase.shenase_takhsis, '1997411')
        self.assertEqual(purchase.weight, 14994)
        self.assertEqual(purchase.amount_paid, 1424430000)
        
        # بررسی ایجاد لاگ پردازش
        processing_log = ExcelProcessingLog.objects.filter(excel_file=self.bge_file).first()
        self.assertIsNotNone(processing_log)
        self.assertTrue(processing_log.success)
        self.assertEqual(processing_log.records_processed, 1)
        self.assertEqual(processing_log.records_created, 1)
    
    def test_process_bge_file_with_existing_purchase(self):
        """
        تست پردازش فایل با خرید موجود
        """
        # ایجاد یک مشتری از قبل
        customer = Customer.objects.create(
            phone_number='9132017353',
            name='محمد موجود',
            field_of_activity='chicken',
            sms_preference=True
        )
        
        # ایجاد یک خرید از قبل
        purchase = Purchase.objects.create(
            purchase_number='2148123',
            customer=customer,
            weight=10000,
            cargo=self.cargo_product,
            amount_paid=1000000000,
            payment_method='نقدی',
            type='bazaargah'
        )
        
        # آماده‌سازی mock برای pandas.read_html
        with patch('excel_manager.views.bge_file_views.pd.read_html') as mock_read_html:
            # ساختن دیتافریم تست
            df = pd.DataFrame({
                'کد': ['2148123'],
                'وزن کل خرید': [14994],
                'مبلغ پرداختی': [1424430000],
                'کد کوتاژ': ['35408055'],
                'شناسه تخصیص': ['1997411'],
                'نام خریدار': ['محمد تستی'],
                'شماره همراه خریدار': ['09132017353'],
                'آدرس تحویل': ['اصفهان، خیابان تست، پلاک 1'],
                'کد ملی تحویل': ['1282915053'],
                'شماره هماهنگی تحویل': ['09132017353'],
                'شیوه پرداخت': ['نقدی']
            })
            mock_read_html.return_value = [df]
            
            # ساخت درخواست POST
            request = self.factory.post(
                reverse('excel_manager:process_bge_file', args=[self.bge_file.id])
            )
            request.user = self.user
            
            # فراخوانی تابع process_bge_file
            response = process_bge_file(request, self.bge_file.id)
            
            # بررسی نتایج
            self.assertEqual(response.status_code, 302)  # تغییر مسیر بعد از موفقیت
            
            # بررسی به‌روزرسانی خرید موجود
            purchase.refresh_from_db()
            self.assertEqual(purchase.weight, 14994)
            self.assertEqual(purchase.amount_paid, 1424430000)
            self.assertEqual(purchase.shenase_takhsis, '1997411')
            
            # بررسی ایجاد لاگ پردازش
            processing_log = ExcelProcessingLog.objects.filter(excel_file=self.bge_file).first()
            self.assertIsNotNone(processing_log)
            self.assertTrue(processing_log.success)
            self.assertEqual(processing_log.records_processed, 1)
            self.assertEqual(processing_log.records_updated, 1)
    
    @patch('excel_manager.views.bge_file_views.pd.read_html')
    def test_process_bge_file_with_missing_columns(self, mock_read_html):
        """
        تست پردازش فایل با ستون‌های ناقص
        """
        # ساختن دیتافریم ناقص
        df = pd.DataFrame({
            'کد': ['2148123'],
            'وزن کل خرید': [14994],
            # ستون مبلغ پرداختی حذف شده
            'کد کوتاژ': ['35408055'],
            'نام خریدار': ['محمد تستی'],
            'شماره همراه خریدار': ['09132017353']
            # سایر ستون‌ها حذف شده‌اند
        })
        mock_read_html.return_value = [df]
        
        # ساخت درخواست POST
        request = self.factory.post(
            reverse('excel_manager:process_bge_file', args=[self.bge_file.id])
        )
        request.user = self.user
        
        # فراخوانی تابع process_bge_file
        response = process_bge_file(request, self.bge_file.id)
        
        # بررسی نتایج - باید خطا داده شود
        self.assertEqual(response.status_code, 302)  # تغییر مسیر به صفحه لیست
        
        # بررسی عدم پردازش فایل
        self.bge_file.refresh_from_db()
        self.assertFalse(self.bge_file.is_processed)
        
        # بررسی ایجاد لاگ پردازش با خطا
        processing_log = ExcelProcessingLog.objects.filter(excel_file=self.bge_file).first()
        self.assertIsNotNone(processing_log)
        self.assertFalse(processing_log.success)
    
    @patch('excel_manager.views.bge_file_views.pd.read_html')
    def test_process_bge_file_with_cottage_mismatch(self, mock_read_html):
        """
        تست پردازش فایل با کوتاژ نامطابق
        """
        # ساختن دیتافریم با کوتاژ متفاوت
        df = pd.DataFrame({
            'کد': ['2148123'],
            'وزن کل خرید': [14994],
            'مبلغ پرداختی': [1424430000],
            'کد کوتاژ': ['12345678'],  # کوتاژ متفاوت با کوتاژ محصول
            'شناسه تخصیص': ['1997411'],
            'نام خریدار': ['محمد تستی'],
            'شماره همراه خریدار': ['09132017353'],
            'آدرس تحویل': ['اصفهان، خیابان تست، پلاک 1'],
            'کد ملی تحویل': ['1282915053'],
            'شماره هماهنگی تحویل': ['09132017353'],
            'شیوه پرداخت': ['نقدی']
        })
        mock_read_html.return_value = [df]
        
        # ساخت درخواست POST
        request = self.factory.post(
            reverse('excel_manager:process_bge_file', args=[self.bge_file.id])
        )
        request.user = self.user
        
        # فراخوانی تابع بررسی مطابقت کوتاژ ها
        with patch('excel_manager.views.bge_file_views.messages.error') as mock_messages:
            response = process_bge_file(request, self.bge_file.id)
            
            # بررسی که پیام خطای عدم مطابقت کوتاژ نمایش داده شود
            mock_messages.assert_called()

    @patch('excel_manager.views.bge_file_views.pd.read_html')
    def test_process_bge_file_with_duplicate_shenase_takhsis(self, mock_read_html):
        """
        تست پردازش فایل با شناسه تخصیص تکراری
        """
        # ایجاد یک مشتری و خرید از قبل با شناسه تخصیص مشخص
        customer = Customer.objects.create(
            phone_number='9132017353',
            name='مشتری قبلی',
            field_of_activity='chicken',
            sms_preference=True
        )
        
        Purchase.objects.create(
            purchase_number='111111',
            customer=customer,
            shenase_takhsis='1997411',  # شناسه تخصیص تکراری
            weight=10000,
            cargo=self.cargo_product,
            amount_paid=1000000000,
            payment_method='نقدی',
            type='bazaargah'
        )
        
        # ساختن دیتافریم با شناسه تخصیص تکراری
        df = pd.DataFrame({
            'کد': ['2148123'],
            'وزن کل خرید': [14994],
            'مبلغ پرداختی': [1424430000],
            'کد کوتاژ': ['35408055'],
            'شناسه تخصیص': ['1997411'],  # شناسه تخصیص تکراری
            'نام خریدار': ['محمد تستی'],
            'شماره همراه خریدار': ['09987654321'],  # شماره متفاوت
            'آدرس تحویل': ['اصفهان، خیابان تست، پلاک 1'],
            'کد ملی تحویل': ['1282915053'],
            'شماره هماهنگی تحویل': ['09132017353'],
            'شیوه پرداخت': ['نقدی']
        })
        mock_read_html.return_value = [df]
        
        # ساخت درخواست POST
        request = self.factory.post(
            reverse('excel_manager:process_bge_file', args=[self.bge_file.id])
        )
        request.user = self.user
        
        # فراخوانی تابع process_bge_file
        response = process_bge_file(request, self.bge_file.id)
        
        # رکوردهای قبل از پردازش باید همچنان باقی بمانند
        self.assertEqual(Purchase.objects.filter(shenase_takhsis='1997411').count(), 1)
        self.assertEqual(Purchase.objects.filter(purchase_number='2148123').count(), 0)

    @patch('pandas.read_html')
    def test_process_bge_file_with_invalid_html(self, mock_read_html):
        """
        تست پردازش فایل با HTML نامعتبر
        """
        # ایجاد یک فایل با محتوای HTML نامعتبر
        invalid_html_content = "این یک فایل HTML نامعتبر است"
        
        with open(os.path.join(settings.MEDIA_ROOT, 'invalid_html.xls'), 'w', encoding='utf-8') as f:
            f.write(invalid_html_content)
            
        invalid_file = SimpleUploadedFile(
            name="invalid_html.xls",
            content=invalid_html_content.encode('utf-8'),
            content_type="application/vnd.ms-excel"
        )
        
        # ایجاد رکورد فایل در دیتابیس
        invalid_bge_file = BGExcelFile.objects.create(
            user=self.user,
            title='فایل نامعتبر',
            file=invalid_file,
            description='فایل با HTML نامعتبر',
            cargo=self.cargo_product
        )
        
        # تنظیم mock برای ایجاد خطا
        mock_read_html.side_effect = Exception("HTML نامعتبر")
        
        # ساخت درخواست POST
        request = self.factory.post(
            reverse('excel_manager:process_bge_file', args=[invalid_bge_file.id])
        )
        request.user = self.user
        
        # استفاده از patch برای messages
        with patch('excel_manager.views.bge_file_views.messages.error') as mock_messages:
            response = process_bge_file(request, invalid_bge_file.id)
            
            # بررسی فراخوانی error message
            mock_messages.assert_called()
            
            # بررسی وضعیت فایل
            invalid_bge_file.refresh_from_db()
            self.assertFalse(invalid_bge_file.is_processed)

    def test_get_excel_columns(self):
        """
        تست تابع get_excel_columns
        """
        from excel_manager.views.bge_file_views import get_excel_columns
        
        # ایجاد فایل اکسل تست
        with open(os.path.join(settings.MEDIA_ROOT, 'test_excel_columns.xls'), 'w', encoding='utf-8') as f:
            f.write(self.sample_html_content)
        
        # فراخوانی تابع
        columns = get_excel_columns(os.path.join(settings.MEDIA_ROOT, 'test_excel_columns.xls'))
        
        # بررسی ستون‌های بازگشتی
        expected_columns = ['کد', 'وزن کل خرید', 'تاریخ خرید', 'قیمت هر واحد', 'شماره پیگیری', 
                           'استان', 'شهرستان', 'مبلغ پرداختی', 'شماره حساب خریدار', 'کد کوتاژ', 
                           'شناسه تخصیص', 'نام خریدار', 'شماره همراه خریدار', 'آدرس تحویل', 
                           'کد ملی تحویل', 'شماره هماهنگی تحویل', 'شیوه پرداخت']
        
        # بررسی که تمامی ستون‌های مورد انتظار وجود داشته باشند
        for column in expected_columns:
            self.assertIn(column, columns) 