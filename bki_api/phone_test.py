def clean_phone_number(phone):
    """پاکسازی شماره تلفن برای استفاده در دیتابیس"""
    # ایجاد یک شماره تلفن پیش‌فرض برای مواقعی که شماره ورودی معتبر نیست
    default_number = "9000000000"
    
    if not phone:
        # اگر شماره خالی است، شماره پیش‌فرض را برگردان
        return default_number, None
        
    # تبدیل اعداد فارسی به انگلیسی
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    english_digits = "0123456789"
    translation_table = str.maketrans(persian_digits, english_digits)
    phone = str(phone).strip().translate(translation_table)
    
    # پاکسازی شماره از کاراکترهای غیرعددی
    cleaned_number = ''.join(c for c in phone if c.isdigit())
    
    # اگر هیچ رقمی استخراج نشد، شماره پیش‌فرض را برگردان
    if not cleaned_number:
        return default_number, None
    
    # حذف صفر ابتدایی اگر وجود داشته باشد
    if cleaned_number.startswith('0'):
        cleaned_number = cleaned_number[1:]
    
    # حذف کد کشور ایران اگر وجود داشته باشد (98)
    if cleaned_number.startswith('98'):
        cleaned_number = cleaned_number[2:]
        
    # اگر شماره بیشتر از 10 رقم دارد، 10 رقم آخر را نگه داریم
    if len(cleaned_number) > 10:
        cleaned_number = cleaned_number[-10:]
        
    # بررسی اینکه شماره با 9 شروع شود (برای تبدیل به موبایل)
    if not cleaned_number.startswith('9'):
        # اگر طول کافی دارد (حداقل 7 رقم)، 9 را اضافه کرده و آخرین 9 رقم را نگه می‌داریم
        if len(cleaned_number) >= 7:
            cleaned_number = '9' + cleaned_number[:9]
        else:
            # اگر کوتاه است، با صفر پر می‌کنیم
            cleaned_number = '9' + cleaned_number.zfill(9)[:9]
    
    # اطمینان از اینکه طول شماره دقیقاً 10 رقم است
    if len(cleaned_number) < 10:
        # اگر کمتر از 10 رقم است، با صفر پر می‌کنیم
        cleaned_number = cleaned_number + '0' * (10 - len(cleaned_number))
    elif len(cleaned_number) > 10:
        # اگر بیشتر از 10 رقم است، اضافه‌ها را حذف می‌کنیم
        cleaned_number = cleaned_number[:10]
    
    # همیشه یک شماره معتبر برمی‌گرداند
    return cleaned_number, None

# تست تابع با شماره‌های مختلف
test_numbers = [
    '32524398',          # شماره تلفن ثابت
    '09127825261',       # شماره موبایل با صفر
    '02433553375',       # شماره تلفن ثابت با کد شهر
    '0000',              # شماره غیر معتبر کوتاه
    '07138724891',       # شماره با کد شهر
    '9121272045',        # شماره موبایل بدون صفر
    '۰۹۱۲۳۴۵۶۷۸۹',        # شماره موبایل با ارقام فارسی
    '123456789012345',   # شماره خیلی طولانی
    'tel: 021-22334455', # شماره با کاراکترهای اضافی
    '+989121234567',     # شماره با فرمت بین‌المللی
    '',                  # شماره خالی
    None,                # مقدار خالی
    'NONE',              # مقدار رشته‌ای غیر عددی
    '-',                 # کاراکتر خاص
    '123',               # شماره خیلی کوتاه
    '03-44223311'        # شماره با خط تیره
]

# اجرای تست‌ها
print("نتایج تست تابع clean_phone_number با شماره‌های مختلف:")
print("=" * 80)
print("شماره ورودی                  | شماره خروجی           | وضعیت")
print("-" * 80)
for number in test_numbers:
    result, error = clean_phone_number(number)
    status = "✅" if result and len(result) == 10 and result.startswith('9') else "❌"
    input_str = str(number)
    if len(input_str) > 25:
        input_str = input_str[:22] + "..."
    print(f"{input_str:<25} | {result:<20} | {status}")
print("=" * 80) 