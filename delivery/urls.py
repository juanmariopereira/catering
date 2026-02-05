from django.urls import path
from . import views

app_name = 'delivery'

urlpatterns = [
    path('', views.RutaListView.as_view(), name='lista'),
    path('ruta/<int:ruta_id>/', views.ruta_imprimible, name='ruta_imprimible'),
    path('ruta/<str:fecha_str>/<int:entregador_id>/', views.ruta_por_fecha_entregador, name='ruta_fecha_entregador'),
]
