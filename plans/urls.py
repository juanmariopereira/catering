from django.urls import path
from . import views

app_name = 'plans'

urlpatterns = [
    path('', views.PlanListView.as_view(), name='lista'),
    path('crear/', views.PlanCreateView.as_view(), name='crear'),
    path('<int:pk>/editar/', views.PlanUpdateView.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.PlanDeleteView.as_view(), name='eliminar'),
]
