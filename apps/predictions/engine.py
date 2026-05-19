"""
Moteur de prévision récursive (cf. notebook §7).

Construit les 48 features attendues par les modèles entraînés :
- 17 numériques : precip/temp/humidite courantes + lags 1,2 + inc_lag 1,2,3
  + precip_roll2/3 + mois_sin/cos + precip_lag1_x_temp_lag1
- 31 OHE district : dist_District <nom> (Bogo = référence omise)

Applique la substitution récursive h=1, 2, 3 où les lags d'incidence aux
horizons futurs sont remplacés par les prévisions des horizons antérieurs,
et où les covariables climatiques futures sont substituées par la
climatologie mensuelle de référence.
"""
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .ml_loader import get_artefacts, get_climatologie, get_model


def predict_recursive(
    algo: str,
    district_nom: str,
    historic_df: pd.DataFrame,
    horizons: List[int] = [1, 2, 3],
) -> Dict[int, Dict[str, Any]]:
    """
    Prévision récursive d'incidence pour un district aux horizons demandés.

    Args:
        algo: 'RF' ou 'XGB'
        district_nom: nom complet du district (avec préfixe 'District ')
        historic_df: DataFrame historique trié par date, contenant :
            date, annee, mois, incidence, precip_mensuel, temp_moy, humidite, population
        horizons: liste des horizons à prédire (typiquement [1, 2, 3])

    Returns:
        {h: {'date_cible': date, 'mois_cible': int, 'annee_cible': int,
             'incidence': float}, ...}
    """
    model = get_model(algo)
    artefacts = get_artefacts()
    climato = get_climatologie()

    if model is None or artefacts is None:
        return {}

    features_all: List[str] = artefacts['features']

    df = historic_df.sort_values('date').reset_index(drop=True).copy()
    last_date = pd.to_datetime(df['date'].iloc[-1])

    # Climatologie de référence pour ce district (un seul df pré-filtré)
    if climato is not None and not climato.empty:
        clim_d = climato[climato['district'] == district_nom].set_index('mois')
    else:
        clim_d = pd.DataFrame()

    # Historique des incidences (dernière valeur en index [-1])
    inc_history = df['incidence'].tolist()
    precip_history = df['precip_mensuel'].tolist()
    temp_history = df['temp_moy'].tolist()
    hum_history = df['humidite'].tolist()

    results: Dict[int, Dict[str, Any]] = {}

    # Buffers étendus par les prévisions au fur et à mesure
    inc_extended = list(inc_history)
    precip_extended = list(precip_history)
    temp_extended = list(temp_history)
    hum_extended = list(hum_history)

    for h in sorted(horizons):
        # ----- Date cible -----
        target_date = (last_date + pd.DateOffset(months=h)).normalize()
        target_month = int(target_date.month)
        target_year = int(target_date.year)
        prev_month = int((target_date - pd.DateOffset(months=1)).month)
        prev2_month = int((target_date - pd.DateOffset(months=2)).month)

        # ----- Lags incidence (récursifs sur les prévisions précédentes) -----
        # À l'horizon h, on a déjà ajouté h-1 prévisions à inc_extended
        # Donc la dernière valeur (index -1) = obs courante ou pred précédente
        inc_lag1 = inc_extended[-1]
        inc_lag2 = inc_extended[-2] if len(inc_extended) >= 2 else inc_lag1
        inc_lag3 = inc_extended[-3] if len(inc_extended) >= 3 else inc_lag2

        # ----- Climat futur : substitution par climatologie -----
        def _clim(month_num: int, var: str, fallback: float) -> float:
            if month_num in clim_d.index:
                v = clim_d.loc[month_num, var]
                return float(v.iloc[0]) if hasattr(v, 'iloc') else float(v)
            return fallback

        precip_now = _clim(target_month, 'precip_clim', precip_extended[-1])
        temp_now = _clim(target_month, 'temp_clim', temp_extended[-1])
        hum_now = _clim(target_month, 'hum_clim', hum_extended[-1])

        # Lags climat : substitution par climatologie pour h>1 (cf. notebook §7)
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

        # ----- Moyennes glissantes -----
        precip_roll2 = (precip_now + precip_lag1) / 2
        precip_roll3 = (precip_now + precip_lag1 + precip_lag2) / 3

        # ----- Saisonnalité (sin/cos sur le mois cible) -----
        mois_sin = np.sin(2 * np.pi * target_month / 12)
        mois_cos = np.cos(2 * np.pi * target_month / 12)

        # ----- Interaction climat -----
        precip_lag1_x_temp_lag1 = precip_lag1 * temp_lag1

        # ----- Dictionnaire des features numériques -----
        feat_vals: Dict[str, float] = {
            'precip_mensuel': precip_now,
            'temp_moy': temp_now,
            'humidite': hum_now,
            'inc_lag1': inc_lag1,
            'inc_lag2': inc_lag2,
            'inc_lag3': inc_lag3,
            'precip_lag1': precip_lag1,
            'precip_lag2': precip_lag2,
            'temp_lag1': temp_lag1,
            'temp_lag2': temp_lag2,
            'hum_lag1': hum_lag1,
            'hum_lag2': hum_lag2,
            'precip_roll2': precip_roll2,
            'precip_roll3': precip_roll3,
            'mois_sin': mois_sin,
            'mois_cos': mois_cos,
            'precip_lag1_x_temp_lag1': precip_lag1_x_temp_lag1,
        }

        # ----- Vecteur de features dans l'ordre EXACT attendu par le modèle -----
        ohe_col = f'dist_{district_nom}'   # ex : 'dist_District Mokolo'
        X_row: List[float] = []
        for feat in features_all:
            if feat in feat_vals:
                X_row.append(feat_vals[feat])
            elif feat.startswith('dist_'):
                X_row.append(1.0 if feat == ohe_col else 0.0)
            else:
                X_row.append(0.0)

        X_df = pd.DataFrame([X_row], columns=features_all)

        # ----- Prédiction -----
        try:
            pred = float(model.predict(X_df)[0])
        except Exception:
            # Fallback : moyenne du même mois calendaire dans l'historique
            same_month = df[df['mois'] == target_month]
            pred = float(same_month['incidence'].mean()) if not same_month.empty else 0.0

        pred = max(0.0, pred)   # incidence non négative

        # ----- Stockage et mise à jour des buffers pour l'horizon suivant -----
        results[h] = {
            'horizon': h,
            'date_cible': target_date.date(),
            'mois_cible': target_month,
            'annee_cible': target_year,
            'incidence': round(pred, 3),
        }

        inc_extended.append(pred)
        precip_extended.append(precip_now)
        temp_extended.append(temp_now)
        hum_extended.append(hum_now)

    return results
