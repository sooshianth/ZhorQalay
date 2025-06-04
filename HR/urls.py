from django.urls import path
from HR.views import weekly_attendance, employee_profile

urlpatterns = [
    path('attendance/', weekly_attendance.daily_attendance_view, name='weekly_attendance_view'),
    path('attendance/download/', weekly_attendance.download_attendance_report, name='download_attendance_report'),
    path('attendance/pending/', weekly_attendance.pending_approvals_view, name='pending_approvals'),
    path('attendance/approve/<int:attendance_id>/', weekly_attendance.approve_attendance, name='approve_attendance'),
    path('attendance/summary/', weekly_attendance.attendance_summary_view, name='attendance_summary'),
    path('attendance/clear-approvals/', weekly_attendance.clear_approval_references, name='clear_approval_references'),
    path('attendance/delete/<int:attendance_id>/', weekly_attendance.delete_attendance, name='delete_attendance'),
    path('attendance/history/<int:attendance_id>/', weekly_attendance.attendance_history_view, name='attendance_history_view'),
    path('employee/profile/', employee_profile.employee_profile_view, name='employee_profile'),
]
