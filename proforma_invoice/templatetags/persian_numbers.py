from django import template

register = template.Library()

@register.filter
def persian_number(value):
    """تبدیل اعداد انگلیسی به فارسی"""
    if value is None:
        return ''
    
    # تبدیل به رشته
    value_str = str(value)
    
    # جدول تبدیل
    english_digits = '0123456789'
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    translation_table = str.maketrans(english_digits, persian_digits)
    
    return value_str.translate(translation_table)


@register.filter
def persian_price(value):
    """فرمت کردن قیمت با جداکننده هزارگان و تبدیل به فارسی"""
    try:
        # حذف اعشار و تبدیل به عدد صحیح
        value = int(float(value))
        
        # فرمت کردن با کاما
        formatted = f"{value:,}"
        
        # تبدیل اعداد و کاما به فارسی
        english_chars = '0123456789,'
        persian_chars = '۰۱۲۳۴۵۶۷۸۹٬'
        translation_table = str.maketrans(english_chars, persian_chars)
        
        return formatted.translate(translation_table)
    except (ValueError, TypeError):
        return persian_number(value)

