"""
URL configuration for base project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

from base import views as base_views

urlpatterns = [
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
    path('dashboard/', base_views.dashboard, name='dashboard'),
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('clients/', include('clients.urls')),
    path('contracts/', include('contracts.urls')),
    path('plans/', include('plans.urls')),
    path('diets/', include('diets.urls')),
    path('recipes/', include('recipes.urls')),
    path('routes/', include('routes.urls')),
    path('kitchen/', include('kitchen.urls')),
    path('delivery/', include('delivery.urls')),
    path('planning/', include('planning.urls')),
    path('purchases/', include('purchases.urls')),
    path('billing/', include('billing.urls')),
]
