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
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

from base import views as base_views

urlpatterns = [
    path('', base_views.home_redirect, name='home'),
    path('dashboard/', base_views.dashboard, name='dashboard'),
    path('feriados/', base_views.FeriadoListView.as_view(), name='feriado_lista'),
    path('feriados/nuevo/', base_views.FeriadoCreateView.as_view(), name='feriado_crear'),
    path('feriados/<int:pk>/editar/', base_views.FeriadoUpdateView.as_view(), name='feriado_editar'),
    path('feriados/<int:pk>/eliminar/', base_views.FeriadoDeleteView.as_view(), name='feriado_eliminar'),
    path('parametros/', base_views.parametros_sistema, name='parametros_sistema'),
    path('parametros/nuevo/', base_views.parametro_crear, name='parametro_crear'),
    path('parametros/<int:pk>/editar/', base_views.parametro_editar, name='parametro_editar'),
    path('historial/', base_views.historial_acciones, name='historial_acciones'),
    path('usuarios/', base_views.UserListView.as_view(), name='user_lista'),
    path('usuarios/crear/', base_views.UserCreateView.as_view(), name='user_crear'),
    path('usuarios/<int:pk>/editar/', base_views.UserUpdateView.as_view(), name='user_editar'),
    path('usuarios/<int:pk>/eliminar/', base_views.UserDeleteView.as_view(), name='user_eliminar'),
    path('admin/', admin.site.urls),
    path('accounts/login/', base_views.CustomLoginView.as_view(), name='login'),
    path('accounts/sin-acceso/', base_views.sin_acceso, name='sin_acceso'),
    path('accounts/entregador-sin-asignar/', base_views.entregador_sin_asignar, name='entregador_sin_asignar'),
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
    path('api/', include('routing.urls')),
]
if getattr(settings, 'DEBUG', False):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = 'base.views.page_not_found'
