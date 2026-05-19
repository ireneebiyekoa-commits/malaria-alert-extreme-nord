"""Client pour l'API NASA POWER (données climatiques mensuelles)."""
import logging
from datetime import date
from typing import Dict, List, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def fetch_climatic_data(
    longitude: float,
    latitude: float,
    annee: int,
    mois: int,
) -> Optional[Dict[str, float]]:
    """
    Récupère les données climatiques mensuelles pour un point géographique.

    Returns:
        {'temp_moy': X, 'humidite': Y, 'precip_mensuel': Z} ou None si erreur
    """
    params = {
        'parameters': ','.join(settings.NASA_POWER_PARAMETERS),
        'community': 'AG',
        'longitude': longitude,
        'latitude': latitude,
        'start': annee,
        'end': annee,
        'format': 'JSON',
    }

    try:
        response = requests.get(
            settings.NASA_POWER_BASE_URL,
            params=params,
            timeout=settings.NASA_POWER_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        params_data = data.get('properties', {}).get('parameter', {})
        mois_key = f"{annee}{mois:02d}"

        temp = params_data.get('T2M', {}).get(mois_key)
        rh = params_data.get('RH2M', {}).get(mois_key)
        precip = params_data.get('PRECTOTCORR', {}).get(mois_key)

        # NASA renvoie -999 pour les valeurs manquantes
        if temp is None or temp == -999:
            return None

        # Conversion précip : mm/jour → mm/mois
        from calendar import monthrange
        nb_jours = monthrange(annee, mois)[1]

        return {
            'temp_moy': round(float(temp), 2),
            'humidite': round(float(rh), 2) if rh and rh != -999 else 0.0,
            'precip_mensuel': round(float(precip) * nb_jours, 2) if precip and precip != -999 else 0.0,
        }
    except Exception as exc:
        logger.error(f"Erreur NASA POWER ({latitude}, {longitude}, {annee}-{mois}): {exc}")
        return None


def fetch_for_all_districts(districts, annee: int, mois: int) -> Dict[int, Dict[str, float]]:
    """Récupère les données climatiques pour une liste de districts."""
    results = {}
    for d in districts:
        data = fetch_climatic_data(d.longitude, d.latitude, annee, mois)
        if data:
            results[d.id] = data
    return results
