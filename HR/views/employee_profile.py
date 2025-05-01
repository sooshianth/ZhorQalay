from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from HR.EmployeeAttendanceModel import WeeklyAttendance
from django.db.models import Sum
from core.decorators.decorators import role_required

@login_required
def employee_profile_view(request):
    """نمایش پروفایل کارمند"""
    employee = request.user.employee
    
    # محاسبه مجموع ساعات ماه جاری
    from datetime import datetime
    current_month = datetime.now().strftime('%Y-%m')
    current_month_hours = WeeklyAttendance.objects.filter(
        employee=request.user,
        week_start_date__startswith=current_month
    ).aggregate(Sum('total_hours'))['total_hours__sum'] or 0
    
    return render(request, 'employee_profile.html', {
        'employee': employee,
        'user': request.user,
        'current_month_hours': current_month_hours
    }) 