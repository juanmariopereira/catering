from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    path('', views.CobroListView.as_view(), name='cobro_lista'),
    path('cobro/crear/', views.CobroCreateView.as_view(), name='cobro_crear'),
    path('cobro/<int:pk>/', views.CobroDetailView.as_view(), name='cobro_detalle'),
    path('cobro/<int:pk>/editar/', views.CobroUpdateView.as_view(), name='cobro_editar'),
    path('cobro/<int:pk>/eliminar/', views.CobroDeleteView.as_view(), name='cobro_eliminar'),
    path('pago/', views.PagoListView.as_view(), name='pago_lista'),
    path('pago/crear/', views.PagoCreateView.as_view(), name='pago_crear'),
    path('pago/<int:pk>/editar/', views.PagoUpdateView.as_view(), name='pago_editar'),
    path('pago/<int:pk>/eliminar/', views.PagoDeleteView.as_view(), name='pago_eliminar'),
    path('dashboard/', views.dashboard_cobranza, name='dashboard'),
    path('reporte/', views.reporte_cobranza, name='reporte'),
]
