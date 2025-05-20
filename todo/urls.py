from django.urls import path, include
from django.views.generic.base import RedirectView
from .views import todo_list_view
   

 # Todo list endpoints
urlpatterns = [
    path('todos/', todo_list_view.todo_dashboard_view, name='todo_dashboard'),
    path('todos/create/', todo_list_view.create_todo_view, name='create_todo'),
    path('todos/completed/', todo_list_view.completed_todos_view, name='completed_todos'),
    path('todos/change-status/<int:task_id>/', todo_list_view.change_todo_status, name='change_todo_status'),
    path('todos/toggle-status/', todo_list_view.toggle_todo_status, name='toggle_todo_status'),
    path('todos/list/', todo_list_view.todo_list_view, name='todo_list'),
    path('todos/<int:task_id>/', todo_list_view.todo_detail_view, name='todo_detail'),
    path('todos/<int:task_id>/edit/', todo_list_view.edit_todo_view, name='edit_todo'),
    path('todos/search/', todo_list_view.search_todos, name='search_todos'),
    path('todos/analytics/', todo_list_view.todo_analytics_view, name='todo_analytics'),
    path('todos/categories/', todo_list_view.manage_categories_view, name='manage_categories'),
]