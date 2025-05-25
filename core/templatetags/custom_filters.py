# core/templatetags/custom_filters.py
from django import template

register = template.Library()

def number_to_words(num):
    units = ["", "هزار", "میلیون", "میلیارد", "تریلیون"]
    ones = ["", "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه"]
    teens = ["ده", "یازده", "دوازده", "سیزده", "چهارده", "پانزده", "شانزده", "هفده", "هجده", "نوزده"]
    tens = ["", "ده", "بیست", "سی", "چهل", "پنجاه", "شصت", "هفتاد", "هشتاد", "نود"]
    hundreds = ["", "صد", "دویست", "سیصد", "چهارصد", "پانصد", "ششصد", "هفتصد", "هشتصد", "نهصد"]

    def convert_chunk(chunk):
        if chunk == 0:
            return ""
        words = []
        if chunk // 100 > 0:
            words.append(hundreds[chunk // 100])
            chunk %= 100
        if chunk // 10 > 1:
            words.append(tens[chunk // 10])
            chunk %= 10
        if chunk // 10 == 1:
            words.append(teens[chunk % 10])
            chunk = 0
        if chunk > 0:
            words.append(ones[chunk])
        return " و ".join(words)

    if num == 0:
        return "صفر"

    words = []
    chunk_index = 0
    while num > 0:
        chunk = num % 1000
        if chunk != 0:
            chunk_words = convert_chunk(chunk)
            if units[chunk_index] != "":
                chunk_words += " " + units[chunk_index]
            words.append(chunk_words)
        num = num // 1000
        chunk_index += 1

    return " و ".join(reversed(words))

@register.filter
def to_persian_words(value):
    try:
        num = int(value)//10
        return number_to_words(num) + " تومان"
    except (ValueError, TypeError):
        return value

@register.filter
def to_persian_words_weight(value):
    try:
        num = int(value)//1000
        return number_to_words(num) + " تن"
    except (ValueError, TypeError):
        return value

@register.filter
def add_commas(value):
    try:
        num = int(value)
        return f"{num:,}"
    except (ValueError, TypeError):
        return value

@register.filter
def split(value, arg):
    """
    فیلتر برای جدا کردن یک رشته با یک جداکننده مشخص
    
    مثال استفاده:
    {{ "محمد,علی,رضا"|split:"," }}
    
    این فیلتر رشته را به لیستی از مقادیر تبدیل می‌کند.
    """
    return value.split(arg)

@register.filter
def to_persian_digits(value):
    return str(value).replace("0", "۰").replace("1", "۱").replace("2", "۲").replace("3", "۳").replace("4", "۴").replace("5", "۵").replace("6", "۶").replace("7", "۷").replace("8", "۸").replace("9", "۹")

@register.filter
def sum_attribute(queryset, attribute):
    return sum(getattr(obj, attribute) for obj in queryset) if queryset else 0

@register.filter
def average(queryset, attribute):
    if not queryset or not queryset.exists():
        return 0
    total = sum(getattr(obj, attribute) for obj in queryset)
    return total / queryset.count() if queryset.count() > 0 else 0


@register.filter
def length(value):
    """
    Returns the length of a list or string.
    """
    try:
        return len(value)
    except (ValueError, TypeError):
        return 0 