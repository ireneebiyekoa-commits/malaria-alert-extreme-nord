"""Page À propos — guide et méthodologie."""
from django.shortcuts import render


def index(request):
    return render(request, 'about/index.html')


def methodologie(request):
    return render(request, 'about/methodologie.html')


def guide(request):
    return render(request, 'about/guide.html')
