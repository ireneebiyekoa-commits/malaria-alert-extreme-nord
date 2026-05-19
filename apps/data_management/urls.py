from django.urls import path

from . import views

app_name = 'data_management'

urlpatterns = [
    path('', views.index, name='index'),
    path('template-excel/', views.telecharger_template, name='telecharger_template'),
    path('importer/', views.importer_donnees, name='importer'),
]
