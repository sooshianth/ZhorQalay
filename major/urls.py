from django.urls import path
from .views.non_bazargah_purchase_list_view import non_bazargah_purchase_list

urlpatterns = [
    path('non-bazargah-purchases/', non_bazargah_purchase_list, name='non_bazargah_purchase_list'),
]
