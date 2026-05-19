"""
Tableau de bord — KPI, carte choroplèthe, séries temporelles climat-incidence, CCF.
Conforme au mémoire §2.3.4.5 (4 zones).
"""
from datetime import date

import numpy as np
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, F, FloatField, Max, Min, Sum
from django.db.models.functions import Cast
from django.http import JsonResponse
from django.shortcuts import render

from apps.core.models import District, Meteo, Observation, Prevision
from apps.core.utils import filter_by_user_role, format_mois_annee


@login_required
def index(request):
    """Page principale du tableau de bord."""
    user = request.user

    obs_qs = filter_by_user_role(Observation.objects.all(), user)

    # ----- KPI -----
    derniere_obs = obs_qs.order_by('-date').first()
    derniere_date = derniere_obs.date if derniere_obs else None

    # Incidence régionale moyenne (12 derniers mois)
    inc_moy_recente = 0.0
    if derniere_date:
        twelve_months_ago_idx = max(0, len(list(obs_qs.values_list('date', flat=True).distinct())) - 12)
        recent_obs = obs_qs.filter(date__year=derniere_date.year)
        if recent_obs.exists():
            total_cas = sum(o.cas_confirmes for o in recent_obs)
            total_pop = sum(o.population for o in recent_obs)
            inc_moy_recente = (total_cas / total_pop) * 1000 if total_pop else 0.0

    total_cas_periode = int(obs_qs.aggregate(s=Sum('cas_confirmes'))['s'] or 0)

    # District le plus affecté (sur la dernière année observée)
    district_top = None
    if derniere_date:
        year = derniere_date.year
        per_district = {}
        for o in obs_qs.filter(date__year=year):
            per_district.setdefault(o.district.nom, {'cas': 0, 'pop': 0})
            per_district[o.district.nom]['cas'] += o.cas_confirmes
            per_district[o.district.nom]['pop'] += o.population
        if per_district:
            ranked = sorted(
                [(n, (v['cas'] / v['pop']) * 1000 if v['pop'] else 0)
                 for n, v in per_district.items()],
                key=lambda x: x[1], reverse=True
            )
            district_top = {'nom': ranked[0][0].replace('District ', ''),
                            'incidence': round(ranked[0][1], 2)}

    # Districts en alerte rouge sur la dernière prévision
    # (KPI affiché uniquement aux administrateurs : un chef de district ne voit
    #  pas un compte global, mais le statut de son seul district — affiché ailleurs)
    prev_qs = filter_by_user_role(Prevision.objects.all(), user)
    nb_alertes_rouges = 0
    statut_mon_district = None        # pour les chefs de district
    latest_prev_date = prev_qs.aggregate(m=Max('date_origine'))['m']
    if latest_prev_date:
        if user.is_admin:
            nb_alertes_rouges = prev_qs.filter(
                date_origine=latest_prev_date, niveau_alerte='rouge'
            ).values('district').distinct().count()
        elif user.is_chef_district and user.district_id:
            # Statut le plus sévère parmi les horizons pour SON district
            niveaux = list(prev_qs.filter(
                date_origine=latest_prev_date
            ).values_list('niveau_alerte', flat=True))
            if 'rouge' in niveaux:
                statut_mon_district = 'rouge'
            elif 'orange' in niveaux:
                statut_mon_district = 'orange'
            elif niveaux:
                statut_mon_district = 'vert'

    # Taux de complétude des données
    nb_obs = obs_qs.count()
    nb_districts_total = District.objects.count()
    n_periods = obs_qs.values('date').distinct().count()
    expected = (1 if user.is_chef_district else nb_districts_total) * n_periods
    taux_completude = (nb_obs / expected * 100) if expected else 100

    # Districts visibles pour le sélecteur
    if user.is_admin:
        districts_visibles = District.objects.all().order_by('nom')
    else:
        districts_visibles = District.objects.filter(pk=user.district_id) if user.district_id \
                             else District.objects.none()

    annees_dispo = sorted(set(obs_qs.values_list('annee', flat=True)))

    context = {
        'kpi': {
            'incidence_moyenne': round(inc_moy_recente, 2),
            'total_cas': total_cas_periode,
            'district_top': district_top,
            'nb_alertes_rouges': nb_alertes_rouges,
            'statut_mon_district': statut_mon_district,
            'taux_completude': round(taux_completude, 1),
            'derniere_periode': format_mois_annee(derniere_date) if derniere_date else '—',
        },
        'districts': districts_visibles,
        'annees_dispo': annees_dispo,
        'annee_courante': annees_dispo[-1] if annees_dispo else date.today().year,
        'is_admin': user.is_admin,
    }
    return render(request, 'dashboard/index.html', context)


# ============================================================
# API JSON pour les graphiques Chart.js / Leaflet
# ============================================================
@login_required
def api_carte_incidence(request):
    """Incidence moyenne annuelle par district (pour la carte choroplèthe)."""
    user = request.user
    annee = int(request.GET.get('annee', date.today().year))

    obs_qs = filter_by_user_role(
        Observation.objects.filter(annee=annee), user
    ).select_related('district')

    par_district = {}
    for o in obs_qs:
        par_district.setdefault(o.district.nom, {'cas': 0, 'pop_sum': 0, 'n': 0, 'd': o.district})
        par_district[o.district.nom]['cas'] += o.cas_confirmes
        par_district[o.district.nom]['pop_sum'] += o.population
        par_district[o.district.nom]['n'] += 1

    data = []
    for nom, v in par_district.items():
        inc_moy = (v['cas'] / v['pop_sum']) * 1000 if v['pop_sum'] else 0.0
        data.append({
            'district': nom,
            'district_court': nom.replace('District ', ''),
            'code_geojson': v['d'].code_geojson,
            'longitude': v['d'].longitude,
            'latitude': v['d'].latitude,
            'cas_total': int(v['cas']),
            'population_moyenne': int(v['pop_sum'] / v['n']) if v['n'] else 0,
            'incidence_moyenne': round(inc_moy, 2),
        })

    return JsonResponse({'annee': annee, 'districts': data})


@login_required
def api_serie_district(request):
    """Série temporelle d'incidence + climat pour un district."""
    user = request.user
    district_id = request.GET.get('district_id')

    if not district_id:
        return JsonResponse({'error': 'district_id requis'}, status=400)

    try:
        district = District.objects.get(pk=district_id)
    except District.DoesNotExist:
        return JsonResponse({'error': 'district inexistant'}, status=404)

    if not user.peut_voir_district(district):
        return JsonResponse({'error': 'accès refusé'}, status=403)

    obs = Observation.objects.filter(district=district).order_by('date')
    meteo = {m.date: m for m in Meteo.objects.filter(district=district)}

    series = []
    for o in obs:
        m = meteo.get(o.date)
        series.append({
            'date': o.date.isoformat(),
            'incidence': round(o.incidence, 3),
            'cas': o.cas_confirmes,
            'temp_moy': m.temp_moy if m else None,
            'humidite': m.humidite if m else None,
            'precip': m.precip_mensuel if m else None,
        })

    return JsonResponse({
        'district': district.nom,
        'population': district.population,
        'series': series,
    })


@login_required
def api_correlation_croisee(request):
    """Fonction de corrélation croisée (CCF) entre incidence et variable climatique."""
    user = request.user
    district_id = request.GET.get('district_id')
    variable = request.GET.get('variable', 'precip')   # precip / temp / humidite
    max_lag = int(request.GET.get('max_lag', 6))

    if not district_id:
        return JsonResponse({'error': 'district_id requis'}, status=400)

    try:
        district = District.objects.get(pk=district_id)
    except District.DoesNotExist:
        return JsonResponse({'error': 'district inexistant'}, status=404)

    if not user.peut_voir_district(district):
        return JsonResponse({'error': 'accès refusé'}, status=403)

    obs = list(Observation.objects.filter(district=district).order_by('date'))
    meteo = {m.date: m for m in Meteo.objects.filter(district=district)}

    incidences = []
    climats = []
    for o in obs:
        m = meteo.get(o.date)
        if m is None:
            continue
        val = {'precip': m.precip_mensuel, 'temp': m.temp_moy,
               'humidite': m.humidite}.get(variable)
        if val is None:
            continue
        incidences.append(o.incidence)
        climats.append(val)

    if len(incidences) < max_lag + 2:
        return JsonResponse({'lags': [], 'ccf': [], 'optimal_lag': None})

    y = np.array(incidences, dtype=float)
    x = np.array(climats, dtype=float)
    y -= y.mean()
    x -= x.mean()
    sy = y.std()
    sx = x.std()
    n = len(y)

    ccf_values = []
    for lag in range(-max_lag, max_lag + 1):
        if lag < 0:
            num = np.sum(y[-lag:] * x[:n + lag])
        else:
            num = np.sum(y[:n - lag] * x[lag:])
        denom = sy * sx * n
        ccf_values.append(num / denom if denom else 0.0)

    lags = list(range(-max_lag, max_lag + 1))
    abs_vals = [abs(v) for v in ccf_values]
    optimal = lags[int(np.argmax(abs_vals))]

    return JsonResponse({
        'lags': lags,
        'ccf': [round(v, 4) for v in ccf_values],
        'optimal_lag': optimal,
        'variable': variable,
    })


@login_required
def api_heatmap_district_mois(request):
    """
    Heatmap incidence district x mois calendaire (profils saisonniers).

    Si le paramètre `district_id` est fourni, seul ce district est inclus
    (utilisé quand le filtre district est actif côté UI).
    """
    user = request.user
    district_id = request.GET.get('district_id')

    obs_qs = filter_by_user_role(Observation.objects.all(), user).select_related('district')

    # Filtre district demandé par l'utilisateur
    if district_id:
        try:
            d_obj = District.objects.get(pk=district_id)
            if not user.peut_voir_district(d_obj):
                return JsonResponse({'error': 'accès refusé'}, status=403)
            obs_qs = obs_qs.filter(district_id=district_id)
        except District.DoesNotExist:
            return JsonResponse({'error': 'district inexistant'}, status=404)

    grid = {}
    counts = {}
    for o in obs_qs:
        key = (o.district.nom, o.mois)
        grid[key] = grid.get(key, 0.0) + o.incidence
        counts[key] = counts.get(key, 0) + 1

    districts = sorted({d for d, _ in grid.keys()})
    mois = list(range(1, 13))
    matrix = []
    for d in districts:
        row = []
        for m in mois:
            v = grid.get((d, m), 0)
            c = counts.get((d, m), 0)
            row.append(round(v / c, 2) if c else 0)
        matrix.append(row)

    return JsonResponse({
        'districts': [d.replace('District ', '') for d in districts],
        'mois': mois,
        'matrix': matrix,
        'district_filter_id': district_id or None,
    })
