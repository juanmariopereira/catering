from django.urls import path
from . import views

app_name = 'diets'

urlpatterns = [
    path('', views.DietaListView.as_view(), name='lista'),
    path('composicion-por-fecha/', views.composicion_por_fecha, name='composicion_por_fecha'),
    path('sugerir-dieta/', views.sugerir_dieta_view, name='sugerir_dieta'),
    path('crear/', views.DietaCreateView.as_view(), name='crear'),
    path('<int:pk>/editar/', views.DietaUpdateView.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.DietaDeleteView.as_view(), name='eliminar'),
    path('tipos-comida/', views.TipoComidaListView.as_view(), name='tipo_comida_lista'),
    path('tipos-comida/crear/', views.TipoComidaCreateView.as_view(), name='tipo_comida_crear'),
    path('tipos-comida/<int:pk>/editar/', views.TipoComidaUpdateView.as_view(), name='tipo_comida_editar'),
    path('tipos-comida/<int:pk>/eliminar/', views.TipoComidaDeleteView.as_view(), name='tipo_comida_eliminar'),
]
