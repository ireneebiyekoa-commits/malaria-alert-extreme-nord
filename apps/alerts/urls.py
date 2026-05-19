from django.urls import path

from . import views

app_name = 'alerts'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/alertes/', views.api_alertes, name='api_alertes'),
    path('export-pdf/', views.export_pdf, name='export_pdf'),
]
