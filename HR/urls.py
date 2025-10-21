from django.urls import path
from HR.views import weekly_attendance, employee_profile, test_delay_view, debug_view, morqk_views, target_schedule_view, manager_dashboard_view

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
    path('test-delay/', test_delay_view.test_delay_mechanism, name='test_delay_mechanism'),
    path('debug-validation/', debug_view.debug_validation_view, name='debug_validation'),
    
    # مسیرهای مرغک
    path('morqk/', morqk_views.morqk_dashboard, name='morqk_dashboard'),
    path('morqk/create/', morqk_views.create_morqk_task, name='create_morqk_task'),
    path('morqk/task/<int:task_id>/', morqk_views.task_detail, name='task_detail'),
    path('morqk/task/<int:task_id>/update/', morqk_views.update_task_status, name='update_task_status'),
    path('morqk/task/<int:task_id>/approve/', morqk_views.approve_task, name='approve_task'),
    path('morqk/task/<int:task_id>/delete/', morqk_views.delete_task, name='delete_task'),
    path('morqk/task/<int:task_id>/edit/', morqk_views.edit_task, name='edit_task'),
    path('morqk/report/', morqk_views.monthly_morqk_report, name='monthly_morqk_report'),
    
    # مسیرهای داشبورد مدیریتی
    path('morqk/manager/', manager_dashboard_view.manager_dashboard, name='manager_dashboard'),
    path('morqk/manager/task/<int:task_id>/', manager_dashboard_view.manager_task_detail, name='manager_task_detail'),
    path('morqk/manager/task/<int:task_id>/change-status/', manager_dashboard_view.manager_change_task_status, name='manager_change_task_status'),
    path('morqk/manager/task/<int:task_id>/edit/', manager_dashboard_view.manager_edit_task, name='manager_edit_task'),
    path('admin/overview/', manager_dashboard_view.admin_overview_dashboard, name='admin_overview_dashboard'),
    
    # مسیرهای هدف ماهانه
    path('target/', target_schedule_view.monthly_target_view, name='monthly_target_view'),
    path('target/create/', target_schedule_view.create_monthly_target, name='create_monthly_target'),
    path('target/edit/<int:target_id>/', target_schedule_view.edit_monthly_target, name='edit_monthly_target'),
    path('target/delete/<int:target_id>/', target_schedule_view.delete_monthly_target, name='delete_monthly_target'),
    
    # مسیرهای برنامه هفتگی
    path('schedule/', target_schedule_view.weekly_schedule_view, name='weekly_schedule_view'),
    path('schedule/create/', target_schedule_view.create_weekly_schedule, name='create_weekly_schedule'),
    path('schedule/edit/<int:schedule_id>/', target_schedule_view.edit_weekly_schedule, name='edit_weekly_schedule'),
    path('schedule/delete/<int:schedule_id>/', target_schedule_view.delete_weekly_schedule, name='delete_weekly_schedule'),
    path('schedule/toggle/<int:schedule_id>/', target_schedule_view.toggle_schedule_status, name='toggle_schedule_status'),
]
