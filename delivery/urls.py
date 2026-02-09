from django.urls import path
from . import views

app_name = 'delivery'

urlpatterns = [
    path('', views.RutaListView.as_view(), name='lista'),
    path('configurar-punto-partida/', views.punto_partida_config, name='punto_partida_config'),
    path('generar-rutas/', views.generar_rutas, name='generar_rutas'),
    path('asignar-pendientes/', views.asignar_pendientes, name='asignar_pendientes'),
    path('distribuir/', views.distribuir_entregas, name='distribuir_entregas'),
    path('ruta/crear/', views.RutaCreateView.as_view(), name='ruta_crear'),
    path('ruta/<int:pk>/editar/', views.RutaUpdateView.as_view(), name='ruta_editar'),
    path('ruta/<int:pk>/cargar-ultima/', views.ruta_cargar_ultima, name='ruta_cargar_ultima'),
    path('ruta/<int:pk>/calcular-orden/', views.ruta_calcular_orden, name='ruta_calcular_orden'),
    path('ruta/<int:pk>/eliminar/', views.RutaDeleteView.as_view(), name='ruta_eliminar'),
    path('ruta/<int:ruta_id>/', views.ruta_imprimible, name='ruta_imprimible'),
    path('ruta/<int:ruta_id>/recalcular-recorrido/', views.ruta_recalcular_recorrido, name='ruta_recalcular_recorrido'),
    path('ruta-cliente/<int:pk>/marcar-entregada/', views.ruta_cliente_marcar_entregada, name='ruta_cliente_marcar_entregada'),
    path('ruta-cliente/<int:pk>/reportar-no-entrega/', views.ruta_cliente_reportar_no_entrega, name='ruta_cliente_reportar_no_entrega'),
    path('ruta/<str:fecha_str>/<int:entregador_id>/', views.ruta_por_fecha_entregador, name='ruta_fecha_entregador'),
]
