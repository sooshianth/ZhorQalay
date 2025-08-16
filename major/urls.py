from django.urls import path
from .views.non_bazargah_purchase_list_view import non_bazargah_purchase_list
from .views.non_bazargah_barnameh_list_view import non_bazargah_barnameh_list

urlpatterns = [
    path('non-bazargah-purchases/', non_bazargah_purchase_list, name='non_bazargah_purchase_list'),
    path('non-bazargah-barnamehs/', non_bazargah_barnameh_list, name='non_bazargah_barnameh_list'),
]
