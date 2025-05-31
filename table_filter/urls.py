from django.urls import path
from . import views

app_name = 'table_filter'

urlpatterns = [
    path('demo/', views.table_filter_demo, name='demo'),
] 