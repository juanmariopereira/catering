from django.urls import path
from . import views

app_name = 'routes'

urlpatterns = [
    path('entregadores/', views.EntregadorListView.as_view(), name='entregador_lista'),
    path('entregadores/crear/', views.EntregadorCreateView.as_view(), name='entregador_crear'),
    path('entregadores/<int:pk>/editar/', views.EntregadorUpdateView.as_view(), name='entregador_editar'),
    path('entregadores/<int:pk>/eliminar/', views.EntregadorDeleteView.as_view(), name='entregador_eliminar'),
]
