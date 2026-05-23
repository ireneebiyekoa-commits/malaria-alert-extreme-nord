"""
Chargement et gestion des modèles ML sérialisés.

Les modèles sont chargés une seule fois en mémoire au démarrage (apps.py:ready).
Les artefacts contiennent :
  - features_all   : 48 features (17 num + 31 OHE district)
  - features_num   : 17 features numériques
  - features_dist  : 31 features OHE 'dist_District XXX'
  - meta_feats     : 6 features du méta-modèle [pred_rf, pred_xgb, pred_diff,
                                                 mois_sin, mois_cos, inc_lag1_orig]
  - best_params_rf, best_params_xgb : hyperparamètres validés
  - inc_lag1_map   : dict (district, date_origine) -> incidence connue à l'origine

Le méta-modèle est un dict {1: Ridge, 2: Ridge, 3: Ridge} — un Ridge par horizon.
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
    'meta_ridge': None,        # dict {1: Ridge, 2: Ridge, 3: Ridge}
    'artefacts': None,
    'climatologie': None,
    'loaded': False,
    'meta_available': False,
    'errors': [],
}


def preload_models() -> bool:
    """Charge les modèles depuis outputs/models/. Retourne True si succès complet."""
    models_dir: Path = settings.ML_MODELS_DIR
    errors = []

    # ---------- Random Forest ----------
    rf_path = models_dir / 'random_forest_final.pkl'
    if rf_path.exists():
        try:
            _ML_CACHE['rf'] = joblib.load(rf_path)
            logger.info(f"Random Forest chargé depuis {rf_path}")
        except Exception as exc:
            errors.append(f"RF: {exc}")
    else:
        errors.append(f"Fichier introuvable : {rf_path}")

    # ---------- XGBoost ----------
    xgb_path = models_dir / 'xgboost_final.pkl'
    if xgb_path.exists():
        try:
            _ML_CACHE['xgb'] = joblib.load(xgb_path)
            logger.info(f"XGBoost chargé depuis {xgb_path}")
        except Exception as exc:
            errors.append(f"XGB: {exc}")
    else:
        errors.append(f"Fichier introuvable : {xgb_path}")

    # ---------- Méta-modèle Ridge (un par horizon) ----------
    meta_path = models_dir / 'meta_ridge_final.pkl'
    if meta_path.exists():
        try:
            meta_obj = joblib.load(meta_path)
            if isinstance(meta_obj, dict):
                _ML_CACHE['meta_ridge'] = meta_obj
                _ML_CACHE['meta_available'] = all(h in meta_obj for h in [1, 2, 3])
                logger.info(f"Méta-modèle Ridge chargé ({len(meta_obj)} horizons) depuis {meta_path}")
            else:
                errors.append(f"Méta-modèle au mauvais format : {type(meta_obj).__name__}")
        except Exception as exc:
            errors.append(f"Meta: {exc}")
    else:
        logger.info(f"Pas de méta-modèle : {meta_path} introuvable (mode RF/XGB uniquement)")

    # ---------- Artefacts ----------
    art_path = models_dir / 'artefacts.pkl'
    if art_path.exists():
        try:
            artefacts = joblib.load(art_path)
            # Compat : si l'ancien schéma (avec 'features' / 'feature_district') est présent,
            # créer les alias pour le nouveau schéma
            if isinstance(artefacts, dict):
                if 'features_all' not in artefacts and 'features' in artefacts:
                    artefacts['features_all'] = artefacts['features']
                if 'features_dist' not in artefacts and 'feature_district' in artefacts:
                    artefacts['features_dist'] = artefacts['feature_district']
            _ML_CACHE['artefacts'] = artefacts
            logger.info(f"Artefacts chargés depuis {art_path}")
        except Exception as exc:
            errors.append(f"Artefacts: {exc}")

    # ---------- Climatologie ----------
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


# ============================================================
# Accesseurs
# ============================================================
def get_model(algo: str) -> Optional[Any]:
    """Retourne le modèle de base (RF ou XGB)."""
    key = 'rf' if algo.upper() in ('RF', 'RANDOMFOREST') else 'xgb'
    return _ML_CACHE.get(key)


def get_meta_ridge(horizon: int = 1) -> Optional[Any]:
    """Retourne le méta-modèle Ridge pour l'horizon donné, ou None s'il n'existe pas."""
    meta = _ML_CACHE.get('meta_ridge')
    if meta is None:
        return None
    return meta.get(horizon)


def get_artefacts() -> Optional[Dict[str, Any]]:
    return _ML_CACHE.get('artefacts')


def get_climatologie() -> Optional[pd.DataFrame]:
    """
    Retourne la climatologie mensuelle de référence par district.

    Source par ordre de priorité :
      1. CSV outputs/models/climatologie_district_mois.csv (si fourni)
      2. Calcul à la volée depuis la table Meteo (et mise en cache)
    """
    cached = _ML_CACHE.get('climatologie')
    if cached is not None and not cached.empty:
        return cached

    # Calcul à la demande depuis la base
    try:
        from apps.core.models import Meteo
        rows = []
        # Agrégation moyenne par (district, mois calendaire)
        from collections import defaultdict
        agg = defaultdict(lambda: {'precip': [], 'temp': [], 'hum': []})
        for m in Meteo.objects.select_related('district').all():
            mois_cal = m.date.month
            key = (m.district.nom, mois_cal)
            agg[key]['precip'].append(m.precip_mensuel)
            agg[key]['temp'].append(m.temp_moy)
            agg[key]['hum'].append(m.humidite)

        for (district, mois), vals in agg.items():
            n = len(vals['precip'])
            rows.append({
                'district': district,
                'mois': mois,
                'precip_clim': sum(vals['precip']) / n if n else 0,
                'temp_clim': sum(vals['temp']) / n if n else 0,
                'hum_clim': sum(vals['hum']) / n if n else 0,
            })

        if rows:
            df = pd.DataFrame(rows)
            _ML_CACHE['climatologie'] = df
            logger.info(f"Climatologie calculée à la volée depuis la BD ({len(df)} entrées)")
            return df
    except Exception as exc:
        logger.warning(f"Calcul climatologie depuis BD échoué : {exc}")

    return None


def is_ready() -> bool:
    return _ML_CACHE.get('loaded', False)


def is_meta_available() -> bool:
    return _ML_CACHE.get('meta_available', False)


def get_status() -> Dict[str, Any]:
    return {
        'loaded': _ML_CACHE.get('loaded'),
        'rf_available': _ML_CACHE.get('rf') is not None,
        'xgb_available': _ML_CACHE.get('xgb') is not None,
        'meta_available': _ML_CACHE.get('meta_available', False),
        'artefacts_available': _ML_CACHE.get('artefacts') is not None,
        'climatologie_available': _ML_CACHE.get('climatologie') is not None,
        'errors': _ML_CACHE.get('errors', []),
    }
