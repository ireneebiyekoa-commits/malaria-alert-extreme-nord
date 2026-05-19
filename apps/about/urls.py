from django.urls import path

from . import views

app_name = 'about'

urlpatterns = [
    path('', views.index, name='index'),
    path('methodologie/', views.methodologie, name='methodologie'),
    path('guide/', views.guide, name='guide'),
]
