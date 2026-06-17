from django.urls import path
from . import views

app_name = 'kitchen'

urlpatterns = [
    path('', views.DetalleCocinaListView.as_view(), name='lista'),
    path('<int:pk>/editar-notas/', views.DetalleCocinaUpdateView.as_view(), name='editar_notas'),
    path('<str:fecha_str>/imprimir/', views.orden_preparacion_imprimible, name='orden_imprimible'),
    path('<str:fecha_str>/', views.detalle_cocina_fecha, name='detalle_fecha'),
]
