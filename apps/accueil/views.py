"""Page d'accueil publique."""
from django.db.models import Avg, Count, Max, Min, Sum
from django.shortcuts import render

from apps.core.models import District, Observation


def index(request):
    """Page d'accueil avec présentation du système et statistiques publiques."""
    nb_districts = District.objects.count()
    agg = Observation.objects.aggregate(
        total_cas=Sum('cas_confirmes'),
        date_min=Min('date'),
        date_max=Max('date'),
        nb_obs=Count('id'),
    )
    context = {
        'nb_districts': nb_districts,
        'total_cas': int(agg['total_cas'] or 0),
        'periode_debut': agg['date_min'],
        'periode_fin': agg['date_max'],
        'nb_observations': agg['nb_obs'],
    }
    return render(request, 'accueil/index.html', context)
