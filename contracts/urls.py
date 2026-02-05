from django.urls import path
from . import views

app_name = 'contracts'

urlpatterns = [
    path('', views.ContratoListView.as_view(), name='lista'),
    path('crear/', views.ContratoCreateView.as_view(), name='crear'),
    path('generar-mensaje/', views.generar_mensaje_cliente_view, name='generar_mensaje'),
    path('<int:pk>/', views.ContratoDetailView.as_view(), name='detalle'),
    path('<int:pk>/dias-extra/', views.ContratoDiasExtraView.as_view(), name='dias_extra'),
    path('<int:pk>/editar/', views.ContratoUpdateView.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.ContratoDeleteView.as_view(), name='eliminar'),
    path('<int:contrato_pk>/pausa/crear/', views.PausaContratoCreateView.as_view(), name='pausa_crear'),
    path('pausa/<int:pk>/editar/', views.PausaContratoUpdateView.as_view(), name='pausa_editar'),
    path('pausa/<int:pk>/eliminar/', views.PausaContratoDeleteView.as_view(), name='pausa_eliminar'),
]
