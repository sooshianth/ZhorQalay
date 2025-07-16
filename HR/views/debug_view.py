from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
import jdatetime
from ..EmployeeAttendanceModel import AttendanceConfiguration
from ..forms.forms import DailyAttendanceForm

@login_required
def debug_validation_view(request):
    """
    Debug view برای بررسی validation
    """
    output = []
    
    try:
        # بررسی config
        config = AttendanceConfiguration.get_active_config()
        output.append(f"✅ Config: {config.allowed_delay_days} روز، استثنا جمعه: {config.consider_friday_exception}")
        output.append(f"✅ Config active: {config.is_active}")
        
        # بررسی تاریخ امروز
        today = jdatetime.date.today()
        output.append(f"✅ Today: {today} (weekday: {today.weekday()})")
        
        # تست چند تاریخ مختلف
        for days_back in range(1, 6):
            test_date = today - jdatetime.timedelta(days=days_back)
            can_register, reason = config.can_register_for_date(test_date)
            status = "✅ مجاز" if can_register else "❌ غیرمجاز"
            output.append(f"{days_back} روز پیش ({test_date}): {status} - {reason}")
        
        # تست فرم
        output.append("\n=== تست فرم ===")
        test_date_str = (today - jdatetime.timedelta(days=3)).strftime('%Y/%m/%d')
        form_data = {
            'date': test_date_str,
            'hours': '8',
            'description': 'تست validation',
        }
        form = DailyAttendanceForm(form_data, user=request.user)
        output.append(f"Form data: {form_data}")
        output.append(f"Form is_valid(): {form.is_valid()}")
        
        if not form.is_valid():
            output.append(f"Form errors: {form.errors}")
        else:
            output.append("✅ Form is valid")
            
    except Exception as e:
        output.append(f"❌ Error: {str(e)}")
        import traceback
        output.append(traceback.format_exc())
    
    # نمایش نتایج
    html_output = "<pre>" + "\n".join(output) + "</pre>"
    return HttpResponse(html_output, content_type='text/html; charset=utf-8') 