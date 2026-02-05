from django.urls import path
from . import views

app_name = 'recipes'

urlpatterns = [
    path('', views.RecetaListView.as_view(), name='lista'),
    path('crear/', views.RecetaCreateView.as_view(), name='crear'),
    path('<int:pk>/', views.RecetaDetailView.as_view(), name='detalle'),
    path('<int:pk>/editar/', views.RecetaUpdateView.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.RecetaDeleteView.as_view(), name='eliminar'),
    path('ingredientes/', views.IngredienteListView.as_view(), name='ingrediente_lista'),
    path('ingredientes/crear/', views.IngredienteCreateView.as_view(), name='ingrediente_crear'),
    path('ingredientes/<int:pk>/editar/', views.IngredienteUpdateView.as_view(), name='ingrediente_editar'),
    path('ingredientes/<int:pk>/eliminar/', views.IngredienteDeleteView.as_view(), name='ingrediente_eliminar'),
]
