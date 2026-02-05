from django.urls import path
from . import views

app_name = 'contracts'

urlpatterns = [
    path('', views.ContratoListView.as_view(), name='lista'),
    path('crear/', views.ContratoCreateView.as_view(), name='crear'),
    path('<int:pk>/editar/', views.ContratoUpdateView.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.ContratoDeleteView.as_view(), name='eliminar'),
]
