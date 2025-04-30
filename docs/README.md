# کانقالای - مستندات پروژه

## معرفی
این پوشه حاوی مستندات پروژه کانقالای است. مستندات با استفاده از [Sphinx](https://www.sphinx-doc.org/) نوشته شده است.

## ساختار پوشه‌ها
- `source/`: فایل‌های منبع مستندات
  - `_static/`: فایل‌های استاتیک (CSS، تصاویر و ...)
  - `_templates/`: قالب‌های HTML
  - `modules/`: مستندات ماژول‌های سیستم
  - `introduction/`: معرفی پروژه
  - سایر پوشه‌ها برای بخش‌های مختلف مستندات
- `build/`: پوشه خروجی ساخت مستندات (پس از اجرای فرآیند ساخت ایجاد می‌شود)

## نصب نیازمندی‌ها
برای استفاده از این مستندات، ابتدا نیاز به نصب Sphinx و پکیج‌های مورد نیاز دارید:

```bash
pip install sphinx sphinx-rtd-theme django-sphinx-autodoc
```

## ساخت مستندات
برای ساخت مستندات به فرمت HTML، دستور زیر را اجرا کنید:

```bash
cd docs
sphinx-build -b html source build/html
```

برای ساخت مستندات به فرمت PDF، دستور زیر را اجرا کنید:

```bash
cd docs
sphinx-build -b latex source build/latex
cd build/latex
make
```

## مشاهده مستندات
پس از ساخت مستندات، می‌توانید فایل‌های HTML تولید شده را در مرورگر خود باز کنید:

```bash
# در لینوکس
xdg-open build/html/index.html

# در مک
open build/html/index.html

# در ویندوز
start build/html/index.html
```

## افزودن به مستندات
برای افزودن محتوای جدید به مستندات، می‌توانید فایل‌های RST جدید ایجاد کنید و آن‌ها را به فایل‌های فهرست موجود اضافه کنید.

مثال:
1. ایجاد فایل جدید: `source/new_section.rst`
2. افزودن محتوا به فایل
3. افزودن مسیر فایل در `toctree` مناسب (معمولاً در فایل `index.rst` بخش مربوطه)

## راهنمای نوشتن RST
برای آشنایی با نحوه نوشتن فایل‌های RST، به [راهنمای reStructuredText Sphinx](https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html) مراجعه کنید.

## پشتیبانی از زبان فارسی
این مستندات از زبان فارسی پشتیبانی می‌کند و جهت متن راست به چپ (RTL) است. استایل‌های مخصوص برای نمایش صحیح متن فارسی در فایل `_static/custom.css` تعریف شده است. 