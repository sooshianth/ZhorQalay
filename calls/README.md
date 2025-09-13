# Call Management System with Asterisk Integration

This module is designed for managing automatic calls with Asterisk integration and advanced queue management.

## 🚀 New Features

### 1. Advanced Call Queue System
- **Queue-based approach**: Create large queues of phone numbers before starting calls
- **Multiple input sources**:
  - 🔍 **Customer Search**: Search existing customers by name or phone number (uses primary phone)
  - ✋ **Manual Entry**: Add phone numbers manually (line by line)
  - 📊 **Excel Upload**: Upload Excel files with phone numbers
  - 🎯 **Smart Suggestions**: System suggests relevant phone numbers
- **Select & Delete**: Click to select numbers, then delete multiple at once
- **Real-time Stats**: See queue count and source breakdown
- **Session Persistence**: Queue persists across page refreshes

### 2. Asterisk Integration
- **Direct API Connection**: Send call requests to Asterisk server
- **JSON Format**: Sends numbers in the exact format you specified
- **Configurable Settings**: Set API URL and authentication key
- **Error Handling**: Comprehensive error logging and user feedback
- **Status Tracking**: Monitor call progress and results

### 3. Improved User Experience
- **Modern UI**: Beautiful, responsive interface with RTL support
- **Toast Notifications**: No more annoying alerts - elegant notifications
- **Visual Feedback**: Clear status indicators and progress bars
- **Single Action**: One button to start calls (removed redundant buttons)

## 🏗️ Technical Architecture

### Models

#### CallQueue
```python
class CallQueue(models.Model):
    session_id = CharField(100)      # Session identifier for grouping
    phone_number = CharField(20)     # Cleaned phone number
    customer = ForeignKey(Customer)  # Optional customer reference
    source = CharField(20)           # Source: customer/manual/excel/suggestion
    added_by = ForeignKey(User)      # User who added the number
    created_at = DateTimeField()     # Creation timestamp
```

#### AutomaticCall (Enhanced)
```python
class AutomaticCall(models.Model):
    # Existing fields...
    asterisk_api_url = CharField(200)    # Asterisk API endpoint
    asterisk_api_key = CharField(100)    # API authentication key
    queue_session_id = CharField(100)    # Reference to call queue
    
    def start_asterisk_call(self):
        """Start call via Asterisk API"""
        # Fetches queue numbers and sends JSON request
        # Format: {"numbers": ["300", "301", "302", "303"]}
```

## 🎯 Usage Guide

### Creating a New Call Campaign

1. **Navigate** to "ایجاد تماس اتوماتیک" (Create Automatic Call)
2. **Build Your Queue** using the right sidebar:
   
   **📱 Add Customers:**
   - Type customer name or phone number
   - Select from search results
   - Primary phone number is automatically used
   
   **✍️ Manual Numbers:**
   - Paste phone numbers (one per line)
   - System automatically cleans and formats numbers
   - Removes country codes and leading zeros
   
   **📄 Excel Upload:**
   - Upload .xlsx or .xls files
   - System automatically detects phone number columns
   - Looks for columns with keywords like "phone", "mobile", "تلفن", "موبایل"
   
   **🎲 Smart Suggestions:**
   - Click to add suggested numbers from active customers
   - Excludes numbers already in queue

3. **Review Your Queue:**
   - See real-time count of numbers
   - Select individual numbers to remove
   - Use "Select All" for bulk operations
   - Visual indicators show source of each number

4. **Configure Call Settings:**
   - Set title, description, and call type
   - Choose scheduling time
   - Configure Asterisk API settings
   - Add message template if needed

5. **Launch Campaign:**
   - Click "ایجاد تماس اتوماتیک" when queue is ready
   - System validates queue has numbers
   - Creates call record with queue reference

### Starting Calls

1. **Go to Call Detail** page
2. **Click "شروع تماس اتوماتیک"** (only available if queue exists)
3. **Confirm** the action
4. **Monitor Progress** through logs and status updates

## 🔧 API Integration

### Asterisk Request Format
```bash
curl -X POST http://192.168.100.128:5000/api/start-dialer \
     -H "Content-Type: application/json" \
     -H "X-API-KEY: YourSuperSecretKeyGoesHere" \
     -d '{"numbers": ["9123456789", "9876543210", "9111222333"]}'
```

### Phone Number Processing
- **Input**: Various formats (with/without country code, with/without leading zero)
- **Processing**: Removes non-digits, country codes (98), leading zeros
- **Output**: Clean 10-digit mobile numbers starting with 9

## 🛠️ Installation & Setup

### Database Migration
```bash
python manage.py makemigrations calls
python manage.py migrate
```

### Required Dependencies
- `requests` - for Asterisk API calls
- `pandas` - for Excel file processing
- `openpyxl` - for Excel file reading

### Admin Interface
All models are registered in Django Admin with:
- List views with filtering and search
- Fieldsets for organized editing
- Readonly fields for system data

## 📊 Features Summary

### ✅ Fixed Issues
- **No more error alerts** on successful deletions
- **Removed page refresh** when deleting numbers
- **Single start button** - removed confusing duplicate buttons
- **Select-then-delete** functionality instead of immediate deletion
- **Better error handling** and user feedback

### 🆕 New Capabilities
- **Queue persistence** across sessions
- **Multi-source number collection**
- **Bulk operations** for queue management
- **Real-time statistics** and feedback
- **Asterisk integration** with proper error handling
- **Smart phone number processing**
- **Modern notification system**

## 🎨 UI/UX Improvements
- **Two-column layout**: Form on left, queue on right
- **Tabbed interface**: Easy switching between input methods
- **Visual feedback**: Progress indicators and status badges
- **Responsive design**: Works on mobile and desktop
- **RTL support**: Proper Persian/Arabic text handling
- **Modern styling**: Clean, professional appearance

This system now provides a complete solution for managing large-scale automatic calling campaigns with Asterisk integration, suitable for marketing, follow-ups, surveys, and notifications.
   - **تب مشتریان**: جستجو و انتخاب مشتریان موجود
   - **تب دستی**: وارد کردن شماره‌ها به صورت متنی
   - **تب اکسل**: آپلود فایل Excel حاوی شماره‌ها
   - **تب پیشنهادی**: اضافه کردن شماره‌های پیشنهادی سیستم
3. فرم اصلی را پر کنید (عنوان، نوع، زمان، ...)
4. تنظیمات Asterisk را وارد کنید
5. "ایجاد تماس اتوماتیک" را کلیک کنید

### 2. شروع تماس با Asterisk
1. در صفحه جزئیات تماس، دکمه "شروع تماس Asterisk" را کلیک کنید
2. سیستم درخواست زیر را به API ارسال می‌کند:

```bash
curl -X POST http://192.168.100.128:5000/api/start-dialer \
     -H "Content-Type: application/json" \
     -H "X-API-KEY: YourSuperSecretKeyGoesHere" \
     -d '{ "numbers": ["9123456789", "9876543210", "9111222333"] }'
```

### 3. مدیریت صف
- امکان حذف شماره‌های تکی از صف
- مشاهده آمار صف (تعداد کل، مشتریان، دستی)
- حفظ صف تا زمان ایجاد تماس نهایی
- پشتیبانی از جلسات کاری (Session)

## API های موجود

### Queue Management APIs
- `POST /api/queue/add-customer/` - افزودن مشتری به صف
- `POST /api/queue/add-manual/` - افزودن شماره‌های دستی
- `POST /api/queue/upload-excel/` - آپلود فایل اکسل
- `POST /api/queue/add-suggestions/` - افزودن پیشنهادات
- `POST /api/queue/remove/` - حذف از صف
- `GET /api/customers/search/` - جستجوی مشتریان

### Call Management APIs
- `POST /automatic/<id>/start-asterisk/` - شروع تماس با Asterisk

## تنظیمات مورد نیاز

### Python Packages
```bash
pip install pandas openpyxl requests
```

### Django Settings
```python
INSTALLED_APPS = [
    # ...
    'calls',
]
```

## ساختار فایل‌ها

```
calls/
├── models.py           # CallQueue, AutomaticCall بروزرسانی شده
├── views.py           # View های صف و Asterisk
├── admin.py           # مدیریت CallQueue در ادمین
├── urls.py            # URL های جدید
└── templates/calls/
    └── create_automatic_call.html  # صفحه ایجاد با صف
```

## مثال استفاده از API

### درخواست Asterisk
```python
import requests
import json

# آماده‌سازی داده‌ها
headers = {
    'Content-Type': 'application/json',
    'X-API-KEY': 'YourSuperSecretKeyGoesHere'
}

data = {
    'numbers': ['9123456789', '9876543210']
}

# ارسال درخواست
response = requests.post(
    'http://192.168.100.128:5000/api/start-dialer',
    headers=headers,
    data=json.dumps(data)
)

if response.status_code == 200:
    print("تماس با موفقیت شروع شد")
else:
    print(f"خطا: {response.status_code}")
```

## لاگ‌ها

تمام فعالیت‌های مربوط به Asterisk در جدول `CallLog` ثبت می‌شود:
- شروع تماس
- خطاهای API
- پاسخ‌های دریافتی

## توسعه آینده

- [ ] پشتیبانی از فرمت‌های بیشتر Excel
- [ ] فیلترینگ پیشرفته مشتریان
- [ ] گزارش‌گیری از نتایج تماس‌ها
- [ ] اتصال مستقیم به AMI Asterisk
- [ ] پشتیبانی از تماس‌های زمان‌بندی شده
