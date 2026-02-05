from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    path('', views.FacturaListView.as_view(), name='factura_lista'),
    path('factura/crear/', views.FacturaCreateView.as_view(), name='factura_crear'),
    path('factura/<int:pk>/', views.FacturaDetailView.as_view(), name='factura_detalle'),
    path('factura/<int:pk>/editar/', views.FacturaUpdateView.as_view(), name='factura_editar'),
    path('factura/<int:pk>/eliminar/', views.FacturaDeleteView.as_view(), name='factura_eliminar'),
    path('pago/', views.PagoListView.as_view(), name='pago_lista'),
    path('pago/crear/', views.PagoCreateView.as_view(), name='pago_crear'),
    path('pago/<int:pk>/editar/', views.PagoUpdateView.as_view(), name='pago_editar'),
    path('pago/<int:pk>/eliminar/', views.PagoDeleteView.as_view(), name='pago_eliminar'),
    path('dashboard/', views.dashboard_cobranza, name='dashboard'),
    path('reporte/', views.reporte_cobranza, name='reporte'),
]
