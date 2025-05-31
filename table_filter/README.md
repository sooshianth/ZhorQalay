# Table Filter App

این اپ یک سیستم فیلتر پیشرفته و **کاملاً عمومی** برای جداول HTML ارائه می‌دهد که روی **هر نوع محتوایی** کار می‌کند.

## 🚀 سریع شروع کنید

فقط **3 خط کد** برای فعال‌سازی:

```html
{% load table_filter_tags %}
{% table_filter_scripts %}

<!-- فقط کلاس enable-filter اضافه کنید -->
<table class="table enable-filter">
    <thead>
        <tr>
            <th>نام</th>
            <th>قیمت</th>
            <th>تاریخ</th>
            <th>وضعیت</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>محصول 1</td>
            <td>100,000</td>
            <td>1402/09/15</td>
            <td><span class="badge bg-success">فعال</span></td>
        </tr>
        <!-- هر تعداد ردیف -->
    </tbody>
</table>

<!-- فیلتر خودکار فعال می‌شود! -->
```

**همین!** فیلتر خودکار:
- ✅ نوع داده‌ها را تشخیص می‌دهد
- ✅ دکمه فیلتر به هر ستون اضافه می‌کند  
- ✅ روی هر محتوایی کار می‌کند

## ویژگی‌های کلیدی

✅ **کاملاً عمومی** - روی هر جدولی با هر نوع محتوا کار می‌کند  
✅ **تشخیص خودکار** - نوع داده‌ها را خودکار تشخیص می‌دهد  
✅ **بدون تنظیم** - فقط یک خط کد برای فعال‌سازی  
✅ **پشتیبانی کامل** - متن، عدد، تاریخ، وضعیت، بولین  

## نصب

```python
# settings.py
INSTALLED_APPS = [
    # ... other apps
    'table_filter.apps.TableFilterConfig',
]

STATICFILES_DIRS = [
    # ... other directories
    BASE_DIR / "table_filter/static",
]
```

## استفاده ساده (توصیه شده)

### روش 1: فعال‌سازی همه جداول

```html
{% load table_filter_tags %}

<!-- بارگذاری اسکریپت‌ها -->
{% table_filter_scripts %}

<!-- هر جدولی که دارید -->
<table class="table table-striped">
    <thead>
        <tr>
            <th>نام کالا</th>
            <th>قیمت</th>
            <th>تاریخ</th>
            <th>وضعیت</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>لپ تاپ</td>
            <td>1,200,000</td>
            <td>1402/08/15</td>
            <td><span class="badge bg-success">فعال</span></td>
        </tr>
        <!-- ... سایر ردیف‌ها ... -->
    </tbody>
</table>

<!-- فعال‌سازی فیلتر برای همه جداول -->
{% enable_table_filter %}
```

### روش 2: فعال‌سازی با کلاس

```html
<!-- اضافه کردن کلاس به جدول -->
<table class="table table-striped enable-filter">
    <!-- محتوای جدول -->
</table>

<!-- فیلتر خودکار فعال می‌شود -->
```

## نمونه‌های مختلف محتوا

### جدول فروش

```html
<table class="table enable-filter">
    <thead>
        <tr>
            <th>مشتری</th>
            <th>مبلغ فروش</th>
            <th>تاریخ</th>
            <th>وضعیت پرداخت</th>
            <th>فعال</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>احمد رضایی</td>
            <td>850,000</td>
            <td>1402/09/20</td>
            <td><span class="badge bg-success">پرداخت شده</span></td>
            <td>بله</td>
        </tr>
        <tr>
            <td>فاطمه محمدی</td>
            <td>1,250,000</td>
            <td>1402/09/18</td>
            <td><span class="badge bg-warning">در انتظار</span></td>
            <td>خیر</td>
        </tr>
    </tbody>
</table>
```

### جدول کارمندان

```html
<table class="table enable-filter">
    <thead>
        <tr>
            <th>نام و نام خانوادگی</th>
            <th>سن</th>
            <th>حقوق</th>
            <th>بخش</th>
            <th>وضعیت</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><a href="/employee/1">علی احمدی</a></td>
            <td>28</td>
            <td>3,500,000</td>
            <td>فناوری</td>
            <td>فعال</td>
        </tr>
        <tr>
            <td><a href="/employee/2">مریم صادقی</a></td>
            <td>35</td>
            <td>4,200,000</td>
            <td>حسابداری</td>
            <td>مرخصی</td>
        </tr>
    </tbody>
</table>
```

### جدول محصولات

```html
<table class="table enable-filter">
    <thead>
        <tr>
            <th>کد محصول</th>
            <th>نام محصول</th>
            <th>موجودی</th>
            <th>قیمت واحد</th>
            <th>دسته‌بندی</th>
            <th>در دسترس</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>P001</td>
            <td>گوشی موبایل</td>
            <td>25</td>
            <td>2,500,000 تومان</td>
            <td>الکترونیک</td>
            <td><input type="checkbox" checked disabled></td>
        </tr>
        <tr>
            <td>P002</td>
            <td>کتاب برنامه‌نویسی</td>
            <td>0</td>
            <td>120,000 تومان</td>
            <td>کتاب</td>
            <td><input type="checkbox" disabled></td>
        </tr>
    </tbody>
</table>
```

## استفاده پیشرفته

### تنظیم نوع ستون‌ها

```html
<table class="table">
    <thead>
        <tr>
            <th {% table_filter_column 'customer' 'نام مشتری' 'text' %}>نام مشتری</th>
            <th {% table_filter_column 'amount' 'مبلغ' 'number' %}>مبلغ</th>
            <th {% table_filter_column 'date' 'تاریخ' 'date' %}>تاریخ</th>
            <th {% table_filter_column 'status' 'وضعیت' 'status' %}>وضعیت</th>
        </tr>
    </thead>
    <tbody>
        <!-- محتوای جدول -->
    </tbody>
</table>

{% table_filter_quick_setup 'myTable' %}
```

### تنظیمات سفارشی

```html
{% table_filter_init '#special-table' enable_toast=True enable_summary=True %}
```

## تشخیص خودکار انواع داده

فیلتر خودکار انواع داده‌ها را تشخیص می‌دهد:

- **متن**: هر محتوای متنی
- **عدد**: اعداد با ممیز، جداکننده هزارگان و واحد
- **تاریخ**: تاریخ‌های شمسی و میلادی
- **وضعیت**: Badge ها و برچسب‌های وضعیت
- **بولین**: بله/خیر، فعال/غیرفعال، چک‌باکس

## JavaScript مستقیم

```javascript
// ساده‌ترین روش
enableTableFilters();

// برای جداول خاص
enableTableFilters('.my-tables');

// پیشرفته
const filter = createTableFilter({
    tableSelector: '#myTable',
    enableToast: true,
    enableSummary: true
});
```

## مثال واقعی - جدول خرید

```html
{% load table_filter_tags %}
{% table_filter_scripts %}

<table class="table table-striped enable-filter">
    <thead>
        <tr>
            <th>شماره فاکتور</th>
            <th>تاریخ خرید</th>
            <th>نام فروشنده</th>
            <th>مبلغ کل</th>
            <th>وضعیت</th>
            <th>نوع پرداخت</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>F-1001</td>
            <td>1402/09/15</td>
            <td>شرکت ABC</td>
            <td>2,500,000</td>
            <td><span class="badge bg-success">تایید شده</span></td>
            <td>نقدی</td>
        </tr>
        <tr>
            <td>F-1002</td>
            <td>1402/09/14</td>
            <td>شرکت XYZ</td>
            <td>1,850,000</td>
            <td><span class="badge bg-warning">در انتظار</span></td>
            <td>چکی</td>
        </tr>
        <!-- داده‌های بیشتر -->
    </tbody>
</table>

<!-- فیلتر خودکار فعال می‌شود -->
```

## 🎯 نمونه زنده

برای مشاهده نمونه زنده:

```python
# urls.py اصلی پروژه
path('table-filter/', include('table_filter.urls')),
```

سپس به آدرس `/table-filter/demo/` بروید.

## پشتیبانی

- ✅ تمام مرورگرهای مدرن
- ✅ Bootstrap 4/5
- ✅ Font Awesome
- ✅ jQuery (اختیاری)
- ✅ Django 3.2+

فیلتر کاملاً عمومی است و بدون نیاز به تنظیم روی هر جدولی کار می‌کند! 

# Table Filter with Bulk Edit System

یک سیستم پیشرفته برای فیلتر کردن جداول و ویرایش گروهی داده‌ها با قابلیت آپلود/دانلود اکسل.

## ویژگی‌های اصلی

### 1. فیلتر جدول
- فیلتر کردن خودکار ستون‌ها
- جستجوی سریع و پیشرفته
- مرتب‌سازی ستون‌ها
- نمایش/مخفی کردن ستون‌ها

### 2. ویرایش گروهی (Bulk Edit)
- ویرایش چندین رکورد به‌طور همزمان
- فرم ویرایش پویا بر اساس نوع جدول
- ویرایش با آپلود فایل اکسل
- دانلود قالب اکسل با داده‌های موجود

## نصب و راه‌اندازی

### 1. اضافه کردن به INSTALLED_APPS

```python
INSTALLED_APPS = [
    # ...
    'table_filter',
    # ...
]
```

### 2. اضافه کردن URL ها

```python
# در فایل urls.py اصلی
urlpatterns = [
    # ...
    path('table-filter/', include('table_filter.urls')),
    # ...
]
```

### 3. نصب وابستگی‌ها

```bash
pip install openpyxl
```

## نحوه استفاده

### 1. فیلتر ساده جدول

در template:

```html
{% load table_filter_tags %}

{% block head_styles %}
    {% table_filter_scripts %}
{% endblock %}

<!-- جدول شما -->
<table class="table enable-filter" id="myTable">
    <thead>
        <tr>
            <th data-column-type="text">نام</th>
            <th data-column-type="number">مبلغ</th>
            <th data-column-type="date">تاریخ</th>
        </tr>
    </thead>
    <tbody>
        <!-- داده‌های جدول -->
    </tbody>
</table>

{% block extra_js %}
    {% enable_table_filter %}
{% endblock %}
```

### 2. فیلتر + ویرایش گروهی

```html
{% load table_filter_tags %}

{% block head_styles %}
    {% table_filter_scripts %}
    {% bulk_edit_scripts %}
{% endblock %}

<!-- جدول با چک‌باکس -->
<table class="table enable-filter" id="purchasesTable">
    <thead>
        <tr>
            <th>
                <input type="checkbox" class="select-all-checkbox">
            </th>
            <th data-column-type="text">مشتری</th>
            <th data-column-type="number">مبلغ</th>
            <th data-column-type="date">تاریخ</th>
        </tr>
    </thead>
    <tbody>
        {% for item in items %}
        <tr>
            <td>
                <input type="checkbox" class="row-checkbox" data-id="{{ item.id }}">
            </td>
            <td>{{ item.customer }}</td>
            <td>{{ item.amount }}</td>
            <td>{{ item.date }}</td>
        </tr>
        {% endfor %}
    </tbody>
</table>

{% block extra_js %}
    {% enable_table_filter %}
    {% enable_bulk_edit %}
    
    <script>
    // تنظیم URL های bulk edit
    if (typeof bulkEditManager !== 'undefined') {
        bulkEditManager.config.bulkEditUrl = '{% url "table_filter:bulk_edit" %}';
        bulkEditManager.config.excelUploadUrl = '{% url "table_filter:bulk_edit_excel" %}';
        bulkEditManager.config.downloadTemplateUrl = '{% url "table_filter:bulk_edit_template" %}';
    }
    </script>
{% endblock %}
```

### 3. تنظیمات پیشرفته

```html
{% enable_bulk_edit %}

<script>
// تنظیمات سفارشی
const bulkEditConfig = {
    tableSelector: '.my-custom-table',
    bulkEditUrl: '/custom-bulk-edit/',
    enableToast: true
};

// اعمال تنظیمات
if (typeof bulkEditManager !== 'undefined') {
    Object.assign(bulkEditManager.config, bulkEditConfig);
}
</script>
```

## انواع ستون‌ها

برای درست کار کردن فیلترها، نوع ستون‌ها را مشخص کنید:

| نوع | مثال |
|-----|------|
| `text` | نام، توضیحات |
| `number` | مبلغ، وزن، تعداد |
| `date` | تاریخ‌ها |

```html
<th data-column-type="text">نام مشتری</th>
<th data-column-type="number">مبلغ</th>
<th data-column-type="date">تاریخ ایجاد</th>
```

## ویرایش گروهی

### فیلدهای پشتیبانی شده

برای جدول خریدها (`purchase`):
- کد درون سازمانی (`invoice_id`)
- شماره خرید (`purchase_number`)
- وزن سفارش (`order_weight`)
- قیمت خرید (`company_price`)
- قیمت فروش (`customer_price`)
- وضعیت (`state`)
- فوری (`is_urgent`)
- فاکتور صادر شده (`is_factored`)
- آرشیو شده (`is_archived`)

### آپلود اکسل

1. سطرهای مورد نظر را انتخاب کنید
2. دکمه "ویرایش با اکسل" را کلیک کنید
3. "دانلود قالب اکسل" را کلیک کنید
4. فایل اکسل را با اطلاعات جدید پر کنید
5. فایل پر شده را آپلود کنید

⚠️ **نکته مهم**: ستون ID را تغییر ندهید!

## API Endpoints

### POST `/table-filter/bulk-edit/`
ویرایش گروهی داده‌ها

**پارامترها:**
- `selected_ids[]`: آرایه شناسه‌های انتخاب شده
- `model_name`: نام مدل (اختیاری)
- `app_name`: نام اپ (پیش‌فرض: ERP)
- سایر فیلدها برای به‌روزرسانی

### POST `/table-filter/bulk-edit-excel/`
ویرایش گروهی با فایل اکسل

**پارامترها:**
- `excel_file`: فایل اکسل
- `selected_ids[]`: آرایه شناسه‌های انتخاب شده

### GET `/table-filter/bulk-edit-template/`
دانلود قالب اکسل

**پارامترها:**
- `table_type`: نوع جدول (purchase, customer, barbary)
- `selected_ids`: شناسه‌های انتخاب شده (جدا شده با کاما)

## پیکربندی JavaScript

```javascript
// تنظیمات پیش‌فرض
const defaultConfig = {
    tableSelector: '.enable-filter',
    bulkEditUrl: '/table-filter/bulk-edit/',
    excelUploadUrl: '/table-filter/bulk-edit-excel/',
    downloadTemplateUrl: '/table-filter/bulk-edit-template/',
    enableToast: true
};

// سفارشی‌سازی
window.bulkEditManager = new BulkEditManager({
    tableSelector: '.my-table',
    enableToast: false,
    // تنظیمات دیگر...
});
```

## استایل‌ها

فایل‌های CSS موجود:
- `table_filter.css`: استایل‌های فیلتر جدول
- `bulk_edit.css`: استایل‌های ویرایش گروهی

برای سفارشی‌سازی استایل‌ها:

```css
/* سفارشی‌سازی دکمه‌های bulk edit */
.bulk-edit-actions .btn {
    /* استایل دلخواه */
}

/* سفارشی‌سازی modal */
#bulkEditModal .modal-content {
    /* استایل دلخواه */
}
```

## مثال کامل

```html
{% load table_filter_tags %}

<!DOCTYPE html>
<html>
<head>
    {% table_filter_scripts %}
    {% bulk_edit_scripts %}
</head>
<body>
    <div class="container">
        <h1>لیست خریدها</h1>
        
        <table class="table table-striped enable-filter" id="purchasesTable">
            <thead>
                <tr>
                    <th>
                        <input type="checkbox" class="select-all-checkbox">
                    </th>
                    <th data-column-type="text">مشتری</th>
                    <th data-column-type="number">مبلغ</th>
                    <th data-column-type="date">تاریخ</th>
                    <th data-column-type="text">وضعیت</th>
                </tr>
            </thead>
            <tbody>
                {% for purchase in purchases %}
                <tr>
                    <td>
                        <input type="checkbox" class="row-checkbox" data-id="{{ purchase.id }}">
                    </td>
                    <td>{{ purchase.customer.name }}</td>
                    <td>{{ purchase.amount|add_commas }}</td>
                    <td>{{ purchase.date|date:"Y/m/d" }}</td>
                    <td>{{ purchase.get_state_display }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    {% enable_table_filter %}
    {% enable_bulk_edit %}
    
    <script>
    // تنظیم URL ها
    if (typeof bulkEditManager !== 'undefined') {
        bulkEditManager.config.bulkEditUrl = '{% url "table_filter:bulk_edit" %}';
        bulkEditManager.config.excelUploadUrl = '{% url "table_filter:bulk_edit_excel" %}';
        bulkEditManager.config.downloadTemplateUrl = '{% url "table_filter:bulk_edit_template" %}';
    }
    </script>
</body>
</html>
```

## رفع مشکلات

### مشکلات رایج

**1. دکمه‌های bulk edit نمایش داده نمی‌شوند**
- اطمینان حاصل کنید که `{% bulk_edit_scripts %}` لود شده
- بررسی کنید که جدول کلاس `enable-filter` دارد
- چک‌باکس‌ها باید کلاس `row-checkbox` داشته باشند

**2. خطا در آپلود اکسل**
- اطمینان حاصل کنید که ستون ID وجود دارد
- فرمت فایل باید `.xlsx` یا `.xls` باشد
- بررسی کنید که URL ها درست تنظیم شده‌اند

**3. فیلترها کار نمی‌کنند**
- `data-column-type` را برای هر ستون تنظیم کنید
- اطمینان حاصل کنید که `{% table_filter_scripts %}` لود شده
- `{% enable_table_filter %}` را فراموش نکنید

### دیباگ

```javascript
// بررسی وجود BulkEditManager
if (typeof BulkEditManager !== 'undefined') {
    console.log('BulkEditManager loaded successfully');
} else {
    console.error('BulkEditManager not found');
}

// بررسی تنظیمات
console.log(bulkEditManager.config);
```

## لایسنس

این پروژه تحت لایسنس MIT منتشر شده است. 