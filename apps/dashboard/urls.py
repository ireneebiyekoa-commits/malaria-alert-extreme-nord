from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    # API JSON
    path('api/carte-incidence/', views.api_carte_incidence, name='api_carte_incidence'),
    path('api/serie-district/', views.api_serie_district, name='api_serie_district'),
    path('api/correlation-croisee/', views.api_correlation_croisee, name='api_correlation_croisee'),
    path('api/heatmap/', views.api_heatmap_district_mois, name='api_heatmap'),
]
