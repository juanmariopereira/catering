from django.urls import path
from . import views

app_name = 'planning'

urlpatterns = [
    path('', views.PlanificacionMenuListView.as_view(), name='lista'),
    path('sugerir-menu-ia/', views.sugerir_menu_ia_view, name='sugerir_menu_ia'),
    path('resumen/', views.resumen_por_fecha, name='resumen'),
    path('clientes-por-fecha/', views.clientes_reciben_fecha, name='clientes_por_fecha'),
    path('contratos-sin-entregador/', views.contratos_sin_entregador_fecha, name='contratos_sin_entregador'),
    path('crear/', views.PlanificacionMenuCreateView.as_view(), name='crear'),
    path('<int:pk>/editar/', views.PlanificacionMenuUpdateView.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.PlanificacionMenuDeleteView.as_view(), name='eliminar'),
    path('calendario/', views.calendario_planificacion, name='calendario'),
    path('calendario/<int:year>/<int:month>/', views.calendario_planificacion, name='calendario_mes'),
    path('recetas-por-tipo/', views.recetas_por_tipo_ajax, name='recetas_por_tipo'),
    path('recetas-del-menu/', views.recetas_del_menu_ajax, name='recetas_del_menu'),
]
