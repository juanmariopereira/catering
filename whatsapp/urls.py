from django.urls import path
from . import views

app_name = 'whatsapp'

urlpatterns = [
    path('webhook/', views.webhook, name='webhook'),
    path('reclamos/', views.reclamos_lista, name='reclamos'),
]
