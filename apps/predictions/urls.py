from django.urls import path

from . import views

app_name = 'predictions'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/prevision/', views.api_prevision, name='api_prevision'),
    path('api/analyse-ia/', views.api_analyse_ia, name='api_analyse_ia'),
    path('api/chat/', views.api_chat, name='api_chat'),
    path('api/rapport/', views.api_generer_rapport, name='api_rapport'),
    path('api/export-excel/', views.api_export_excel, name='api_export_excel'),
    path('api/export-excel-global/', views.api_export_excel_global, name='api_export_excel_global'),
]
