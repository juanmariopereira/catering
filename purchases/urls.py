from django.urls import path
from . import views

app_name = 'purchases'

urlpatterns = [
    path('', views.PrevisionCompraListView.as_view(), name='lista'),
    path('crear/', views.PrevisionCompraCreateView.as_view(), name='crear'),
    path('<int:pk>/', views.PrevisionCompraDetailView.as_view(), name='detalle'),
    path('<int:pk>/editar/', views.PrevisionCompraUpdateView.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.PrevisionCompraDeleteView.as_view(), name='eliminar'),
    path('<int:prevision_id>/excel/', views.exportar_excel, name='exportar_excel'),
    path('<int:prevision_id>/pdf/', views.exportar_pdf, name='exportar_pdf'),
]
