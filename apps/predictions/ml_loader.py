"""
Chargement et gestion des modèles ML sérialisés.
Les modèles sont chargés une seule fois en mémoire au démarrage (apps.py:ready).
"""
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import joblib
import pandas as pd
from django.conf import settings

logger = logging.getLogger(__name__)

# Cache global des modèles
_ML_CACHE: Dict[str, Any] = {
    'rf': None,
    'xgb': None,
    'artefacts': None,
    'climatologie': None,
    'loaded': False,
    'errors': [],
}


def preload_models() -> bool:
    """Charge les modèles depuis outputs/models/. Retourne True si succès complet."""
    models_dir: Path = settings.ML_MODELS_DIR
    errors = []

    # Random Forest
    rf_path = models_dir / 'random_forest_final.pkl'
    if rf_path.exists():
        try:
            _ML_CACHE['rf'] = joblib.load(rf_path)
            logger.info(f"Random Forest chargé depuis {rf_path}")
        except Exception as exc:
            errors.append(f"RF: {exc}")
    else:
        errors.append(f"Fichier introuvable : {rf_path}")

    # XGBoost
    xgb_path = models_dir / 'xgboost_final.pkl'
    if xgb_path.exists():
        try:
            _ML_CACHE['xgb'] = joblib.load(xgb_path)
            logger.info(f"XGBoost chargé depuis {xgb_path}")
        except Exception as exc:
            errors.append(f"XGB: {exc}")
    else:
        errors.append(f"Fichier introuvable : {xgb_path}")

    # Artefacts (features, hyperparamètres)
    art_path = models_dir / 'artefacts.pkl'
    if art_path.exists():
        try:
            _ML_CACHE['artefacts'] = joblib.load(art_path)
            logger.info(f"Artefacts chargés depuis {art_path}")
        except Exception as exc:
            errors.append(f"Artefacts: {exc}")

    # Climatologie
    clim_path = models_dir / 'climatologie_district_mois.csv'
    if clim_path.exists():
        try:
            _ML_CACHE['climatologie'] = pd.read_csv(clim_path)
            logger.info(f"Climatologie chargée depuis {clim_path}")
        except Exception as exc:
            errors.append(f"Climato: {exc}")

    _ML_CACHE['errors'] = errors
    _ML_CACHE['loaded'] = (_ML_CACHE['rf'] is not None and _ML_CACHE['xgb'] is not None)

    if not _ML_CACHE['loaded']:
        logger.warning(f"Modèles ML partiellement chargés. Erreurs : {errors}")

    return _ML_CACHE['loaded']


def get_model(algo: str) -> Optional[Any]:
    """Retourne le modèle entraîné pour l'algorithme demandé."""
    key = 'rf' if algo.upper() in ('RF', 'RANDOMFOREST') else 'xgb'
    return _ML_CACHE.get(key)


def get_artefacts() -> Optional[Dict[str, Any]]:
    return _ML_CACHE.get('artefacts')


def get_climatologie() -> Optional[pd.DataFrame]:
    return _ML_CACHE.get('climatologie')


def is_ready() -> bool:
    return _ML_CACHE.get('loaded', False)


def get_status() -> Dict[str, Any]:
    return {
        'loaded': _ML_CACHE.get('loaded'),
        'rf_available': _ML_CACHE.get('rf') is not None,
        'xgb_available': _ML_CACHE.get('xgb') is not None,
        'artefacts_available': _ML_CACHE.get('artefacts') is not None,
        'climatologie_available': _ML_CACHE.get('climatologie') is not None,
        'errors': _ML_CACHE.get('errors', []),
    }
