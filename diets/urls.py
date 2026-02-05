from django.urls import path
from . import views

app_name = 'diets'

urlpatterns = [
    path('', views.DietaListView.as_view(), name='lista'),
    path('crear/', views.DietaCreateView.as_view(), name='crear'),
    path('<int:pk>/editar/', views.DietaUpdateView.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.DietaDeleteView.as_view(), name='eliminar'),
]
