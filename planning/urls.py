from django.urls import path
from . import views

app_name = 'planning'

urlpatterns = [
    path('', views.PlanificacionDietaListView.as_view(), name='lista'),
    path('crear/', views.PlanificacionDietaCreateView.as_view(), name='crear'),
    path('<int:pk>/editar/', views.PlanificacionDietaUpdateView.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.PlanificacionDietaDeleteView.as_view(), name='eliminar'),
    path('calendario/', views.calendario_planificacion, name='calendario'),
    path('calendario/<int:year>/<int:month>/', views.calendario_planificacion, name='calendario_mes'),
]
