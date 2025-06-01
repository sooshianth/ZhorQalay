from django.urls import path
from .views.home_view import home_view, unified_login_view
from .views.logout_view import logout_view
from .views.profile import profile_view

urlpatterns = [
    path('', home_view, name='home_view'),
    path('login/', unified_login_view, name='unified_login'),
    path('logout/', logout_view, name='logout'),
    path('profile/', profile_view, name='welcome_profile'),
]

