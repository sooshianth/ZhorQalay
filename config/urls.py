from django.contrib import admin
from django.urls import path, include
from crm.views import home_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('sales/', include('sales.urls')),
    path('crm/', include('crm.urls')),
    path('', home_view.home_view, name='home_view'),
]
