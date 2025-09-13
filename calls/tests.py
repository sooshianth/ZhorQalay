from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from .models import AutomaticCall, CallCustomer, CallLog
from core.CustomerModel import Customer


class CallsViewsTestCase(TestCase):
    def setUp(self):
        """تنظیم اولیه تست‌ها"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )
        
        # ایجاد یک مشتری تست
        self.customer = Customer.objects.create(
            name='مشتری تست',
            phone='09123456789',
            email='customer@test.com'
        )
        
        # ایجاد یک تماس تست
        self.call = AutomaticCall.objects.create(
            title='تماس تست',
            description='این یک تماس تست است',
            call_type='marketing',
            scheduled_time=timezone.now() + timedelta(hours=1),
            priority=1,
            phone_numbers='09123456789,09987654321',
            message_template='سلام، این یک پیام تست است.',
            created_by=self.user
        )

    def test_dashboard_view(self):
        """تست نمایش داشبورد"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('calls:automatic_calls_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'داشبورد تماس‌های اتوماتیک')

    def test_calls_list_view(self):
        """تست نمایش لیست تماس‌ها"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('calls:automatic_calls_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'تماس تست')

    def test_create_call_view_get(self):
        """تست نمایش فرم ایجاد تماس"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('calls:create_automatic_call'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ایجاد تماس اتوماتیک جدید')

    def test_create_call_view_post(self):
        """تست ایجاد تماس جدید"""
        self.client.login(username='testuser', password='testpass123')
        future_time = timezone.now() + timedelta(hours=2)
        
        data = {
            'title': 'تماس جدید',
            'description': 'توضیحات تماس جدید',
            'call_type': 'follow_up',
            'scheduled_time': future_time.strftime('%Y-%m-%dT%H:%M'),
            'priority': 2,
            'phone_numbers': '09111111111',
            'message_template': 'پیام تست'
        }
        
        response = self.client.post(reverse('calls:create_automatic_call'), data)
        self.assertEqual(response.status_code, 302)  # انتظار ریدایرکت
        
        # بررسی ایجاد تماس در دیتابیس
        self.assertTrue(AutomaticCall.objects.filter(title='تماس جدید').exists())

    def test_call_detail_view(self):
        """تست نمایش جزئیات تماس"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('calls:automatic_call_detail', args=[self.call.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.call.title)

    def test_start_call(self):
        """تست شروع تماس"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('calls:start_automatic_call', args=[self.call.id]))
        self.assertEqual(response.status_code, 302)
        
        # بررسی تغییر وضعیت
        self.call.refresh_from_db()
        self.assertEqual(self.call.status, 'in_progress')

    def test_stop_call(self):
        """تست متوقف کردن تماس"""
        # ابتدا تماس را شروع می‌کنیم
        self.call.status = 'in_progress'
        self.call.start_time = timezone.now()
        self.call.save()
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('calls:stop_automatic_call', args=[self.call.id]))
        self.assertEqual(response.status_code, 302)
        
        # بررسی تغییر وضعیت
        self.call.refresh_from_db()
        self.assertEqual(self.call.status, 'completed')

    def test_api_stats(self):
        """تست API آمار"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('calls:get_call_stats_api'))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('total', data)
        self.assertIn('pending', data)
        self.assertIn('in_progress', data)
        self.assertIn('completed', data)

    def test_filters_in_list_view(self):
        """تست فیلترها در لیست تماس‌ها"""
        self.client.login(username='testuser', password='testpass123')
        
        # تست فیلتر وضعیت
        response = self.client.get(reverse('calls:automatic_calls_list'), {'status': 'pending'})
        self.assertEqual(response.status_code, 200)
        
        # تست فیلتر نوع تماس
        response = self.client.get(reverse('calls:automatic_calls_list'), {'call_type': 'marketing'})
        self.assertEqual(response.status_code, 200)
        
        # تست جستجو
        response = self.client.get(reverse('calls:automatic_calls_list'), {'search': 'تست'})
        self.assertEqual(response.status_code, 200)


class CallsModelsTestCase(TestCase):
    def setUp(self):
        """تنظیم اولیه تست‌ها"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_automatic_call_creation(self):
        """تست ایجاد مدل AutomaticCall"""
        call = AutomaticCall.objects.create(
            title='تماس تست',
            description='توضیحات تست',
            call_type='marketing',
            scheduled_time=timezone.now() + timedelta(hours=1),
            created_by=self.user
        )
        
        self.assertEqual(call.title, 'تماس تست')
        self.assertEqual(call.status, 'pending')
        self.assertEqual(call.total_calls, 0)
        self.assertEqual(call.successful_calls, 0)
        self.assertEqual(call.failed_calls, 0)

    def test_call_log_creation(self):
        """تست ایجاد لاگ تماس"""
        call = AutomaticCall.objects.create(
            title='تماس تست',
            call_type='marketing',
            scheduled_time=timezone.now() + timedelta(hours=1),
            created_by=self.user
        )
        
        log = CallLog.objects.create(
            call=call,
            event_type='created',
            message='تماس ایجاد شد',
            details={'test': 'data'}
        )
        
        self.assertEqual(log.call, call)
        self.assertEqual(log.event_type, 'created')
        self.assertEqual(log.details['test'], 'data')

    def test_call_string_representation(self):
        """تست نمایش رشته‌ای مدل‌ها"""
        call = AutomaticCall.objects.create(
            title='تماس تست',
            call_type='marketing',
            scheduled_time=timezone.now() + timedelta(hours=1),
            created_by=self.user
        )
        
        expected_str = f"تماس تست - {call.get_status_display()}"
        self.assertEqual(str(call), expected_str)
