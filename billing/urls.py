from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    path('', views.FacturaListView.as_view(), name='factura_lista'),
    path('factura/crear/', views.FacturaCreateView.as_view(), name='factura_crear'),
    path('pago/crear/', views.PagoCreateView.as_view(), name='pago_crear'),
    path('dashboard/', views.dashboard_cobranza, name='dashboard'),
    path('reporte/', views.reporte_cobranza, name='reporte'),
]
