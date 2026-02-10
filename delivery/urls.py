from django.urls import path
from . import views

app_name = 'delivery'

urlpatterns = [
    path('', views.RutaListView.as_view(), name='lista'),
    path('asignar-pendientes/', views.asignar_pendientes, name='asignar_pendientes'),
    path('distribuir/', views.distribuir_entregas, name='distribuir_entregas'),
    path('ruta/entregador/<int:entregador_id>/editar/', views.PlantillaRutaUpdateView.as_view(), name='ruta_editar_plantilla'),
    path('ruta/entregador/<int:entregador_id>/calcular-orden/', views.ruta_calcular_orden, name='ruta_calcular_orden'),
    path('ruta/<int:ruta_id>/', views.ruta_imprimible, name='ruta_imprimible'),
    path('ruta/<str:fecha_str>/<int:entregador_id>/', views.ruta_por_fecha_entregador, name='ruta_fecha_entregador'),
    path('ruta/<str:fecha_str>/<int:entregador_id>/recalcular-recorrido/', views.ruta_recalcular_recorrido, name='ruta_recalcular_recorrido'),
    path('entregador/<int:entregador_id>/contrato/<int:contrato_id>/fecha/<str:fecha_str>/marcar-entregada/', views.entregadia_marcar_entregada, name='entregadia_marcar_entregada'),
    path('entregador/<int:entregador_id>/contrato/<int:contrato_id>/fecha/<str:fecha_str>/reportar-no-entrega/', views.entregadia_reportar_no_entrega, name='entregadia_reportar_no_entrega'),
]
