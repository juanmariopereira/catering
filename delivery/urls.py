from django.urls import path
from . import views

app_name = 'delivery'

urlpatterns = [
    path('', views.RutaListView.as_view(), name='lista'),
    path('generar-rutas/', views.generar_rutas, name='generar_rutas'),
    path('asignar-pendientes/', views.asignar_pendientes, name='asignar_pendientes'),
    path('ruta/crear/', views.RutaCreateView.as_view(), name='ruta_crear'),
    path('ruta/<int:pk>/editar/', views.RutaUpdateView.as_view(), name='ruta_editar'),
    path('ruta/<int:pk>/cargar-ultima/', views.ruta_cargar_ultima, name='ruta_cargar_ultima'),
    path('ruta/<int:pk>/eliminar/', views.RutaDeleteView.as_view(), name='ruta_eliminar'),
    path('ruta/<int:ruta_id>/', views.ruta_imprimible, name='ruta_imprimible'),
    path('ruta/<str:fecha_str>/<int:entregador_id>/', views.ruta_por_fecha_entregador, name='ruta_fecha_entregador'),
]
