"""
مدل‌های اپلیکیشن HR
"""

from .EmployeeModel import Employee
from .EmployeeAttendanceModel import (
    WeeklyAttendance,
    TimeRange,
    MonthlyAttendance,
    WorkCalendar,
    Salary,
    AttendanceDocument,
    AttendanceHistory,
    AttendanceConfiguration,
)
from .MorqkModel import MorqkTask, MonthlyMorqkSummary, TaskAssignment

__all__ = [
    'Employee',
    'WeeklyAttendance',
    'TimeRange',
    'MonthlyAttendance',
    'WorkCalendar',
    'Salary',
    'AttendanceDocument',
    'AttendanceHistory',
    'AttendanceConfiguration',
    'MorqkTask',
    'MonthlyMorqkSummary',
    'TaskAssignment',
]

