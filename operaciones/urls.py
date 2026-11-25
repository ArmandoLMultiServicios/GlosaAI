from django.urls import path

from . import usuarios, views

app_name = 'operaciones'

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('analizar/', views.analizar, name='analizar'),
    path('usuarios/', usuarios.lista, name='usuarios'),
    path('usuarios/nuevo/', usuarios.nuevo, name='usuario_nuevo'),
    path('usuarios/<int:pk>/', usuarios.editar, name='usuario_editar'),
    path('usuarios/<int:pk>/eliminar/', usuarios.eliminar, name='usuario_eliminar'),
    path('mi-contrasena/', usuarios.mi_contrasena, name='mi_contrasena'),
]
