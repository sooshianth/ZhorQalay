from django.urls import path
from .views.non_bazargah_purchase_list_view import non_bazargah_purchase_list
from .views.non_bazargah_barnameh_list_view import non_bazargah_barnameh_list
from .views.non_bazargah_purchase_CRUD import (
    non_bazargah_purchase_CRUD_view,
    delete_non_bazargah_purchase_view,
    # upload_non_bazargah_document  # منسوخ شده - حالا درون فرم اصلی handle می‌شود
)
from .views.pdf_views import generate_barnameh_pdf

urlpatterns = [
    path('non-bazargah-purchases/', non_bazargah_purchase_list, name='non_bazargah_purchase_list'),
    path('non-bazargah-barnamehs/', non_bazargah_barnameh_list, name='non_bazargah_barnameh_list'),
    path('non-bazargah-purchase/<int:purchase_id>/', non_bazargah_purchase_CRUD_view, name='non_bazargah_purchase_CRUD'),
    path('non-bazargah-purchase/<int:purchase_id>/delete/', delete_non_bazargah_purchase_view, name='delete_non_bazargah_purchase'),
    path('non-bazargah-purchase/<int:purchase_id>/pdf/', generate_barnameh_pdf, name='generate_barnameh_pdf'),
    # path('non-bazargah-purchase/<int:purchase_id>/upload/', upload_non_bazargah_document, name='upload_non_bazargah_document'),  # منسوخ
]
