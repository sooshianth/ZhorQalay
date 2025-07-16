from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
import jdatetime
from ..EmployeeAttendanceModel import AttendanceConfiguration

@staff_member_required
@login_required
def test_delay_mechanism(request):
    """
    View برای تست مکانیزم تاخیر در ثبت ساعات کاری
    """
    # دریافت تنظیمات فعال
    config = AttendanceConfiguration.get_active_config()
    
    # تاریخ امروز
    today = jdatetime.date.today()
    
    # نام روزهای هفته
    weekday_names = {
        0: 'شنبه',
        1: 'یکشنبه', 
        2: 'دوشنبه',
        3: 'سه‌شنبه',
        4: 'چهارشنبه',
        5: 'پنج‌شنبه',
        6: 'جمعه'
    }
    today_weekday = weekday_names.get(today.weekday(), 'نامشخص')
    
    # تست های مختلف
    test_dates = [
        today,  # امروز
        today - jdatetime.timedelta(days=1),  # دیروز
        today - jdatetime.timedelta(days=2),  # پریروز
        today - jdatetime.timedelta(days=3),  # 3 روز پیش
        today + jdatetime.timedelta(days=1),  # فردا
    ]
    
    test_results = []
    for test_date in test_dates:
        can_register, reason = config.can_register_for_date(test_date)
        days_diff = (today - test_date).days
        test_results.append({
            'date': test_date,
            'days_diff': days_diff,
            'can_register': can_register,
            'reason': reason
        })
    
    # تست خاص برای روز شنبه
    saturday_tests = []
    # شبیه‌سازی شنبه
    saturday = jdatetime.date(1404, 1, 1)
    while saturday.weekday() != 0:  # 0 = شنبه
        saturday += jdatetime.timedelta(days=1)
    
    for days_back in range(1, 5):
        test_date = saturday - jdatetime.timedelta(days=days_back)
        can_register, reason = config.can_register_for_date(test_date)
        saturday_tests.append({
            'days_back': days_back,
            'date': test_date,
            'can_register': can_register,
            'reason': reason
        })
    
    context = {
        'config': config,
        'today': today,
        'today_weekday': today_weekday,
        'test_results': test_results,
        'saturday_tests': saturday_tests,
    }
    
    return render(request, 'test_delay.html', context) 