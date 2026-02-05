from django.urls import path
from . import views

app_name = 'kitchen'

urlpatterns = [
    path('', views.DetalleCocinaListView.as_view(), name='lista'),
    path('<str:fecha_str>/', views.detalle_cocina_fecha, name='detalle_fecha'),
]
