from django.urls import path
from . import views

urlpatterns = [
    path('list/', views.proforma_list, name='proforma_list'),
    path('create/step1/<int:customer_id>/', views.proforma_step1_customer_info, name='proforma_step1'),
    path('create/step2/<int:customer_id>/', views.proforma_step2_product_selection, name='proforma_step2'),
    path('preview/<int:proforma_id>/', views.proforma_preview, name='proforma_preview'),
    path('download/<int:proforma_id>/', views.proforma_download_pdf, name='proforma_download_pdf'),
]

