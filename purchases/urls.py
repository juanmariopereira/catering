from django.urls import path
from . import views

app_name = 'purchases'

urlpatterns = [
    path('', views.PrevisionCompraListView.as_view(), name='lista'),
    path('crear/', views.PrevisionCompraCreateView.as_view(), name='crear'),
    path('<int:pk>/', views.PrevisionCompraDetailView.as_view(), name='detalle'),
    path('<int:prevision_id>/excel/', views.exportar_excel, name='exportar_excel'),
    path('<int:prevision_id>/pdf/', views.exportar_pdf, name='exportar_pdf'),
]
