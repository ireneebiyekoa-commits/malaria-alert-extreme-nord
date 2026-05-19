"""Utilitaires partagés (filtrage par rôle, calculs)."""
from datetime import date

from django.db.models import QuerySet


def filter_by_user_role(queryset: QuerySet, user, district_field: str = 'district') -> QuerySet:
    """
    Filtre un QuerySet selon le rôle de l'utilisateur :
    - admin : aucun filtre
    - chef de district : filtre sur son district uniquement
    """
    if not user.is_authenticated:
        return queryset.none()
    if user.is_admin:
        return queryset
    if user.is_chef_district and user.district_id:
        return queryset.filter(**{district_field: user.district})
    return queryset.none()


def determiner_niveau_alerte(incidence_predite: float, p75: float, p90: float) -> str:
    """Détermine le niveau d'alerte (vert / orange / rouge) selon les seuils OMS."""
    if incidence_predite is None:
        return 'vert'
    if incidence_predite >= p90:
        return 'rouge'
    if incidence_predite >= p75:
        return 'orange'
    return 'vert'


MOIS_FR = {
    1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril',
    5: 'Mai', 6: 'Juin', 7: 'Juillet', 8: 'Août',
    9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre',
}

MOIS_FR_COURT = {
    1: 'Jan', 2: 'Fév', 3: 'Mar', 4: 'Avr', 5: 'Mai', 6: 'Juin',
    7: 'Juil', 8: 'Août', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Déc',
}


def format_mois_annee(d: date) -> str:
    """Formate une date en 'Janvier 2025'."""
    return f"{MOIS_FR[d.month]} {d.year}"
