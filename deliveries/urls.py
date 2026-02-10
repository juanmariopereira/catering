"""
URL configuration for deliveries API (v1).
Mount under /api/v1/
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

app_name = 'deliveries_api'

urlpatterns = [
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('courier/context/', views.CourierContextView.as_view(), name='courier_context'),
    path('events/', views.EventView.as_view(), name='events'),
    path('mobile/version/', views.MobileVersionView.as_view(), name='mobile_version'),
]
