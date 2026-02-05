from django.urls import path
from . import views

app_name = 'recipes'

urlpatterns = [
    path('', views.RecetaListView.as_view(), name='lista'),
    path('crear/', views.RecetaCreateView.as_view(), name='crear'),
    path('<int:pk>/', views.RecetaDetailView.as_view(), name='detalle'),
    path('<int:pk>/editar/', views.RecetaUpdateView.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.RecetaDeleteView.as_view(), name='eliminar'),
    path('tipos-receta/', views.TipoRecetaListView.as_view(), name='tipo_receta_lista'),
    path('tipos-receta/crear/', views.TipoRecetaCreateView.as_view(), name='tipo_receta_crear'),
    path('tipos-receta/<int:pk>/editar/', views.TipoRecetaUpdateView.as_view(), name='tipo_receta_editar'),
    path('tipos-receta/<int:pk>/eliminar/', views.TipoRecetaDeleteView.as_view(), name='tipo_receta_eliminar'),
    path('unidades-medida/', views.UnidadMedidaListView.as_view(), name='unidad_medida_lista'),
    path('unidades-medida/crear/', views.UnidadMedidaCreateView.as_view(), name='unidad_medida_crear'),
    path('unidades-medida/<int:pk>/editar/', views.UnidadMedidaUpdateView.as_view(), name='unidad_medida_editar'),
    path('unidades-medida/<int:pk>/eliminar/', views.UnidadMedidaDeleteView.as_view(), name='unidad_medida_eliminar'),
    path('ingredientes/', views.IngredienteListView.as_view(), name='ingrediente_lista'),
    path('ingredientes/crear/', views.IngredienteCreateView.as_view(), name='ingrediente_crear'),
    path('ingredientes/<int:pk>/editar/', views.IngredienteUpdateView.as_view(), name='ingrediente_editar'),
    path('ingredientes/<int:pk>/eliminar/', views.IngredienteDeleteView.as_view(), name='ingrediente_eliminar'),
]
