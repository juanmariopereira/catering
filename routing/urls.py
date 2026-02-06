"""
URL configuration for routing app (route optimization API).
"""
from django.urls import path

from .views import RouteOptimizeView

app_name = "routing"

urlpatterns = [
    path("routes/optimize", RouteOptimizeView.as_view(), name="optimize"),
]
