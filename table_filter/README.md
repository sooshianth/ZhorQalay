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