# سیستم نمایش لایو قیمت به حروف فارسی

این سیستم برای نمایش لایو قیمت‌ها به حروف فارسی در فرم‌های مالی طراحی شده است.

## ویژگی‌ها

- ✅ تبدیل خودکار عدد به حروف فارسی
- ✅ نمایش لایو هنگام تایپ
- ✅ پشتیبانی از اعداد تا میلیارد
- ✅ انیمیشن‌های زیبا
- ✅ پشتیبانی از حالت تاریک
- ✅ سازگار با فرم‌های Django
- ✅ خودکار تشخیص فیلدهای مبلغ

## نحوه استفاده

### 1. اضافه کردن اسکریپت

```html
<script src="{% static 'fledger/js/live_price_display.js' %}"></script>
```

### 2. فعال‌سازی خودکار

سیستم به صورت خودکار تمام فیلدهای مبلغ را تشخیص می‌دهد و نمایش لایو را اضافه می‌کند.

### 3. فعال‌سازی دستی

```javascript
// برای فیلد خاص
window.livePriceDisplay.attachToInput('#field-id');

// برای چندین فیلد
const inputs = document.querySelectorAll('input[name*="amount"], input[name*="price"]');
inputs.forEach(input => {
    window.livePriceDisplay.attachToInput(`#${input.id}`);
});
```

## فایل‌های بروزرسانی شده

### فایل‌های JavaScript
- `fledger/static/fledger/js/live_price_display.js` - فایل اصلی سیستم

### فایل‌های CSS
- `fledger/static/fledger/css/fledger.css` - استایل‌های نمایش لایو قیمت

### فایل‌های Template
- `fledger/templates/fledger/create_hazinah.html`
- `fledger/templates/fledger/edit_hazinah.html`
- `fledger/templates/fledger/pay_hazinah.html`
- `fledger/templates/fledger/create_transaction.html`
- `fledger/templates/fledger/edit_transaction.html`
- `fledger/templates/fledger/add_invoice.html`
- `fledger/templates/fledger/edit_invoice.html`
- `fledger/templates/fledger/create_invoice.html`

## مثال‌های تبدیل

| عدد | حروف فارسی |
|-----|------------|
| 1000 | یک هزار ریال |
| 1500000 | یک میلیون و پانصد هزار ریال |
| 25000000 | بیست و پنج میلیون ریال |
| 1000000000 | یک میلیارد ریال |
| 1234567890 | یک میلیارد و دویست و سی و چهار میلیون و پانصد و شصت و هفت هزار و هشتصد و نود ریال |

## تنظیمات CSS

```css
.live-price-display {
    /* استایل‌های اصلی */
    background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
    border: 1px solid #0ea5e9;
    color: #0369a1;
    /* ... */
}
```

## تست

برای تست عملکرد، فایل `test_live_price_display.html` را در مرورگر باز کنید.

## پشتیبانی

- مرورگرهای مدرن
- موبایل و تبلت
- حالت تاریک
- فرم‌های پیچیده Django

## نکات مهم

1. سیستم فقط با اعداد مثبت کار می‌کند
2. محدودیت: اعداد بالای 999 میلیارد پشتیبانی نمی‌شوند
3. نمایش فقط هنگام فوکوس روی فیلد فعال می‌شود
4. سازگار با فرم‌های Django و فرم‌ست‌ها
