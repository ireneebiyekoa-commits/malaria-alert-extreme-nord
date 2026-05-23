"""
Moteur de prévision (cf. mémoire §3.2.5 — méta-modèle adaptatif).

Trois modes disponibles :

  - 'RF'   : Random Forest récursif (modèle de base)
  - 'XGB'  : XGBoost récursif (modèle de base)
  - 'META' : Méta-modèle adaptatif (mode recommandé) :
              * h = 1 → Ridge stacking [RF, XGB, écart, sin/cos mois, inc_lag1]
              * h = 2 → XGBoost récursif (le test de Diebold-Mariano §3.2.5.3
                        a confirmé qu'à h=2 le stacking n'apporte rien)
              * h = 3 → XGBoost récursif (idem)

Features attendues :
  - Modèle de base (RF/XGB) : 48 features (17 num + 31 OHE district)
  - Méta-modèle Ridge       : 6 features [pred_rf, pred_xgb, pred_diff,
                                          mois_sin, mois_cos, inc_lag1_orig]
"""
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .ml_loader import (get_artefacts, get_climatologie, get_meta_ridge,
                        get_model, is_meta_available)

# Algorithmes supportés
ALGO_RF = 'RF'
ALGO_XGB = 'XGB'
ALGO_META = 'META'   # méta-modèle adaptatif


# ============================================================
# Construction du vecteur de features (modèle de base)
# ============================================================
def _build_base_features(
    target_date: pd.Timestamp,
    district_nom: str,
    inc_extended: List[float],
    precip_extended: List[float],
    temp_extended: List[float],
    hum_extended: List[float],
    climato_df: pd.DataFrame,
    features_all: List[str],
    h: int,
) -> pd.DataFrame:
    """Construit le vecteur de 48 features pour une prédiction à un horizon h."""
    target_month = int(target_date.month)
    prev_month = int((target_date - pd.DateOffset(months=1)).month)
    prev2_month = int((target_date - pd.DateOffset(months=2)).month)

    # ----- Climatologie de référence pour ce district -----
    if climato_df is not None and not climato_df.empty:
        clim_d = climato_df[climato_df['district'] == district_nom].set_index('mois')
    else:
        clim_d = pd.DataFrame()

    def _clim(month_num: int, var: str, fallback: float) -> float:
        if not clim_d.empty and month_num in clim_d.index:
            v = clim_d.loc[month_num, var]
            return float(v.iloc[0]) if hasattr(v, 'iloc') else float(v)
        return fallback

    # ----- Lags incidence (avec substitution récursive) -----
    inc_lag1 = inc_extended[-1]
    inc_lag2 = inc_extended[-2] if len(inc_extended) >= 2 else inc_lag1
    inc_lag3 = inc_extended[-3] if len(inc_extended) >= 3 else inc_lag2

    # ----- Climat à l'instant cible (substitution par climatologie) -----
    precip_now = _clim(target_month, 'precip_clim', precip_extended[-1])
    temp_now = _clim(target_month, 'temp_clim', temp_extended[-1])
    hum_now = _clim(target_month, 'hum_clim', hum_extended[-1])

    # ----- Lags climat (réels pour h=1, climatologie pour h>1) -----
    if h == 1:
        precip_lag1 = precip_extended[-1]
        precip_lag2 = precip_extended[-2] if len(precip_extended) >= 2 else precip_lag1
        temp_lag1 = temp_extended[-1]
        temp_lag2 = temp_extended[-2] if len(temp_extended) >= 2 else temp_lag1
        hum_lag1 = hum_extended[-1]
        hum_lag2 = hum_extended[-2] if len(hum_extended) >= 2 else hum_lag1
    else:
        precip_lag1 = _clim(prev_month, 'precip_clim', precip_extended[-1])
        precip_lag2 = _clim(prev2_month, 'precip_clim', precip_lag1)
        temp_lag1 = _clim(prev_month, 'temp_clim', temp_extended[-1])
        temp_lag2 = _clim(prev2_month, 'temp_clim', temp_lag1)
        hum_lag1 = _clim(prev_month, 'hum_clim', hum_extended[-1])
        hum_lag2 = _clim(prev2_month, 'hum_clim', hum_lag1)

    # ----- Moyennes glissantes + saisonnalité + interaction -----
    precip_roll2 = (precip_now + precip_lag1) / 2
    precip_roll3 = (precip_now + precip_lag1 + precip_lag2) / 3
    mois_sin = np.sin(2 * np.pi * target_month / 12)
    mois_cos = np.cos(2 * np.pi * target_month / 12)
    precip_lag1_x_temp_lag1 = precip_lag1 * temp_lag1

    feat_vals: Dict[str, float] = {
        'precip_mensuel': precip_now,
        'temp_moy': temp_now,
        'humidite': hum_now,
        'inc_lag1': inc_lag1, 'inc_lag2': inc_lag2, 'inc_lag3': inc_lag3,
        'precip_lag1': precip_lag1, 'precip_lag2': precip_lag2,
        'temp_lag1': temp_lag1, 'temp_lag2': temp_lag2,
        'hum_lag1': hum_lag1, 'hum_lag2': hum_lag2,
        'precip_roll2': precip_roll2, 'precip_roll3': precip_roll3,
        'mois_sin': mois_sin, 'mois_cos': mois_cos,
        'precip_lag1_x_temp_lag1': precip_lag1_x_temp_lag1,
    }

    ohe_col = f'dist_{district_nom}'
    X_row: List[float] = []
    for feat in features_all:
        if feat in feat_vals:
            X_row.append(feat_vals[feat])
        elif feat.startswith('dist_'):
            X_row.append(1.0 if feat == ohe_col else 0.0)
        else:
            X_row.append(0.0)

    return pd.DataFrame([X_row], columns=features_all)


# ============================================================
# Prédiction récursive RF ou XGB
# ============================================================
def predict_recursive(
    algo: str,
    district_nom: str,
    historic_df: pd.DataFrame,
    horizons: List[int] = [1, 2, 3],
) -> Dict[int, Dict[str, Any]]:
    """
    Prévision récursive d'incidence pour RF ou XGB.
    Retourne {h: {'date_cible', 'mois_cible', 'annee_cible', 'incidence'}}
    """
    model = get_model(algo)
    artefacts = get_artefacts()
    climato = get_climatologie()

    if model is None or artefacts is None:
        return {}

    features_all: List[str] = artefacts.get('features_all') or artefacts.get('features', [])

    df = historic_df.sort_values('date').reset_index(drop=True).copy()
    last_date = pd.to_datetime(df['date'].iloc[-1])

    inc_extended = df['incidence'].tolist()
    precip_extended = df['precip_mensuel'].tolist()
    temp_extended = df['temp_moy'].tolist()
    hum_extended = df['humidite'].tolist()

    results: Dict[int, Dict[str, Any]] = {}

    for h in sorted(horizons):
        target_date = (last_date + pd.DateOffset(months=h)).normalize()
        X_df = _build_base_features(
            target_date, district_nom,
            inc_extended, precip_extended, temp_extended, hum_extended,
            climato, features_all, h,
        )
        try:
            pred = float(model.predict(X_df)[0])
        except Exception:
            same_month = df[df['mois'] == int(target_date.month)]
            pred = float(same_month['incidence'].mean()) if not same_month.empty else 0.0

        pred = max(0.0, pred)
        results[h] = {
            'horizon': h,
            'date_cible': target_date.date(),
            'mois_cible': int(target_date.month),
            'annee_cible': int(target_date.year),
            'incidence': round(pred, 3),
        }

        # Mise à jour des buffers pour h+1
        inc_extended.append(pred)
        # Climat futur : utiliser la climatologie pour le mois cible
        if climato is not None and not climato.empty:
            clim_d = climato[climato['district'] == district_nom].set_index('mois')
            tmonth = int(target_date.month)
            if tmonth in clim_d.index:
                precip_extended.append(float(clim_d.loc[tmonth, 'precip_clim']))
                temp_extended.append(float(clim_d.loc[tmonth, 'temp_clim']))
                hum_extended.append(float(clim_d.loc[tmonth, 'hum_clim']))
            else:
                precip_extended.append(precip_extended[-1])
                temp_extended.append(temp_extended[-1])
                hum_extended.append(hum_extended[-1])
        else:
            precip_extended.append(precip_extended[-1])
            temp_extended.append(temp_extended[-1])
            hum_extended.append(hum_extended[-1])

    return results


# ============================================================
# Prédiction méta-modèle (Ridge stacking) à un horizon donné
# ============================================================
def predict_meta_at_horizon(
    district_nom: str,
    historic_df: pd.DataFrame,
    horizon: int,
) -> Optional[Dict[str, Any]]:
    """
    Calcule la prévision du méta-modèle Ridge pour un horizon donné.

    Étapes :
      1. Faire prédire RF et XGB pour cet horizon (récursif)
      2. Calculer les 6 features méta : [pred_rf, pred_xgb, pred_diff,
                                          mois_sin, mois_cos, inc_lag1_orig]
      3. Appliquer Ridge[horizon] sur ces features
    """
    ridge = get_meta_ridge(horizon)
    if ridge is None:
        return None

    # 1. Prédictions des deux modèles de base
    rf_preds = predict_recursive('RF', district_nom, historic_df, horizons=[horizon])
    xgb_preds = predict_recursive('XGB', district_nom, historic_df, horizons=[horizon])
    if horizon not in rf_preds or horizon not in xgb_preds:
        return None

    pred_rf = rf_preds[horizon]['incidence']
    pred_xgb = xgb_preds[horizon]['incidence']

    # 2. Méta-features
    df = historic_df.sort_values('date').reset_index(drop=True)
    last_date = pd.to_datetime(df['date'].iloc[-1])
    target_date = (last_date + pd.DateOffset(months=horizon)).normalize()
    target_month = int(target_date.month)

    pred_diff = pred_xgb - pred_rf
    mois_sin = np.sin(2 * np.pi * target_month / 12)
    mois_cos = np.cos(2 * np.pi * target_month / 12)
    inc_lag1_orig = float(df['incidence'].iloc[-1])

    # Ordre des features (vérifié dans artefacts['meta_feats']) :
    # ['pred_rf', 'pred_xgb', 'pred_diff', 'mois_sin', 'mois_cos', 'inc_lag1_orig']
    # On passe un array numpy (sans noms) car le Ridge a été entraîné sans noms.
    X_meta = np.array([[pred_rf, pred_xgb, pred_diff, mois_sin, mois_cos, inc_lag1_orig]],
                      dtype=float)

    try:
        meta_pred = float(ridge.predict(X_meta)[0])
    except Exception:
        # Fallback : moyenne RF+XGB pondérée
        meta_pred = 0.5 * pred_rf + 0.5 * pred_xgb

    meta_pred = max(0.0, meta_pred)

    return {
        'horizon': horizon,
        'date_cible': target_date.date(),
        'mois_cible': target_month,
        'annee_cible': int(target_date.year),
        'incidence': round(meta_pred, 3),
        'pred_rf': round(pred_rf, 3),
        'pred_xgb': round(pred_xgb, 3),
    }


# ============================================================
# Méta-modèle ADAPTATIF (mode recommandé — cf. §3.2.5.4)
# ============================================================
def predict_adaptive(
    district_nom: str,
    historic_df: pd.DataFrame,
    horizons: List[int] = [1, 2, 3],
) -> Dict[int, Dict[str, Any]]:
    """
    Stratégie adaptative validée par test de Diebold-Mariano (§3.2.5.3) :
      - h = 1 → méta-modèle Ridge (gain RMSE de 3,2% vs XGB)
      - h ≥ 2 → XGBoost direct (stacking devient contre-productif)

    Si le méta-modèle est absent, fallback sur XGBoost pour tous les horizons.
    """
    results: Dict[int, Dict[str, Any]] = {}
    meta_ok = is_meta_available()

    # XGBoost pour les horizons longs (et fallback h=1 si méta indispo)
    xgb_horizons = [h for h in horizons if (h >= 2 or not meta_ok)]
    if xgb_horizons:
        xgb_preds = predict_recursive('XGB', district_nom, historic_df, horizons=xgb_horizons)
        for h, p in xgb_preds.items():
            results[h] = {**p, 'source': 'XGBoost récursif'}

    # Méta-modèle pour h=1 (si dispo)
    if meta_ok and 1 in horizons:
        meta = predict_meta_at_horizon(district_nom, historic_df, horizon=1)
        if meta is not None:
            results[1] = {**meta, 'source': 'Méta-modèle Ridge'}

    return results


# ============================================================
# Dispatcher générique
# ============================================================
def predict(
    algo: str,
    district_nom: str,
    historic_df: pd.DataFrame,
    horizons: List[int] = [1, 2, 3],
) -> Dict[int, Dict[str, Any]]:
    """Point d'entrée unique : choisit la stratégie selon l'algo demandé."""
    algo = (algo or 'META').upper()
    if algo == 'META':
        return predict_adaptive(district_nom, historic_df, horizons)
    return predict_recursive(algo, district_nom, historic_df, horizons)
