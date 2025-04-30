from django.urls import path
from . import views

app_name = 'bki_api'

urlpatterns = [
    path('credentials/', views.credentials_view, name='credentials'),
    path('test-kharid-info/', views.test_kharid_info, name='test_kharid_info'),
] 