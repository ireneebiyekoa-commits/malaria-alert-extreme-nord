"""
Calcule les performances RMSE / MAE / R2 des modèles RF et XGB par validation
walk-forward réelle sur les données en base.

Protocole (cf. mémoire) :
  - Pli 1 : train 2017-2020, test 2021
  - Pli 2 : train 2017-2021, test 2022
  - Pli 3 : train 2017-2022, test 2023
  - Pli 4 : train 2017-2023, test 2024
  - Pli 5 : train 2017-2024, test 2025

Pour chaque pli, on prédit l'incidence aux horizons 1, 2 et 3 mois
pour TOUS les districts, puis on compare aux valeurs observées.
"""
from collections import defaultdict

import numpy as np
import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from apps.core.models import District, Meteo, Observation, Performance
from apps.predictions.engine import predict_recursive
from apps.predictions.ml_loader import is_ready


PLIS = [
    (1, 2017, 2020, 2021),
    (2, 2017, 2021, 2022),
    (3, 2017, 2022, 2023),
    (4, 2017, 2023, 2024),
    (5, 2017, 2024, 2025),
]
HORIZONS = [1, 2, 3]
ALGOS = ['RF', 'XGB']


class Command(BaseCommand):
    help = ("Calcule les métriques RMSE / MAE / R2 par validation walk-forward "
            "sur les données en base.")

    def handle(self, *args, **options):
        if not is_ready():
            self.stderr.write(self.style.ERROR(
                "Les modèles ML ne sont pas chargés. Vérifiez outputs/models/."
            ))
            return

        # Chargement complet en mémoire (par district)
        self.stdout.write("Chargement des observations et météos...")
        all_obs = list(Observation.objects.select_related('district').order_by('district_id', 'date'))
        all_meteo = list(Meteo.objects.all())

        # Index météo par (district_id, date)
        meteo_idx = {(m.district_id, m.date): m for m in all_meteo}

        # Construire les DataFrames par district
        district_dfs = defaultdict(list)
        for o in all_obs:
            m = meteo_idx.get((o.district_id, o.date))
            district_dfs[o.district].append({
                'date': o.date,
                'annee': o.annee,
                'mois': o.mois,
                'incidence': o.incidence,
                'precip_mensuel': m.precip_mensuel if m else 0,
                'temp_moy': m.temp_moy if m else 0,
                'humidite': m.humidite if m else 0,
                'population': o.population,
            })

        # Collecte des prédictions et observations
        rows = []   # (algo, fold, horizon, y_true, y_pred)

        for fold_num, _train_start, train_end_year, test_year in PLIS:
            self.stdout.write(f"\n--- Pli {fold_num}: train <= {train_end_year}, test = {test_year} ---")

            for district, full_rows in district_dfs.items():
                df = pd.DataFrame(full_rows).sort_values('date').reset_index(drop=True)
                if df.empty:
                    continue

                # Pour chaque date d'origine = dernier mois de l'année train ou ultérieur dans test
                # On itère sur tous les mois de l'année de test : pour chaque mois m,
                # date_origine = (m - horizon) mais on simplifie en faisant origine = dernier mois <= test_year-1
                # Avec récursion h=1,2,3 depuis cette origine.

                # On évalue les prévisions issues de plusieurs origines successives dans l'année test
                df_train = df[df['annee'] <= train_end_year].copy()
                df_test = df[df['annee'] == test_year].copy()

                if df_train.empty or df_test.empty or len(df_train) < 6:
                    continue

                # Origines : on glisse l'origine du dernier mois de train jusqu'à test - max(horizon)
                origins = list(df_train['date'].tail(1).values) + list(df_test['date'].iloc[:-max(HORIZONS)].values)

                for origin in origins:
                    origin = pd.to_datetime(origin).date()
                    historic = df[df['date'] <= origin].copy()
                    if len(historic) < 3:
                        continue

                    for algo in ALGOS:
                        try:
                            preds = predict_recursive(algo, district.nom, historic, horizons=HORIZONS)
                        except Exception:
                            continue

                        for h, pred in preds.items():
                            actual_row = df[df['date'] == pred['date_cible']]
                            if actual_row.empty:
                                continue
                            y_true = float(actual_row['incidence'].iloc[0])
                            y_pred = float(pred['incidence'])
                            rows.append((algo, fold_num, h, y_true, y_pred))

        if not rows:
            self.stderr.write(self.style.ERROR("Aucune prédiction calculée — vérifiez les données."))
            return

        # Agrégation par (algo, fold, horizon)
        df_eval = pd.DataFrame(rows, columns=['algo', 'fold', 'horizon', 'y_true', 'y_pred'])

        with transaction.atomic():
            Performance.objects.all().delete()

            self.stdout.write("\nMétriques calculées par (algo, fold, horizon) :")
            for (algo, fold, h), grp in df_eval.groupby(['algo', 'fold', 'horizon']):
                yt = grp['y_true'].values
                yp = grp['y_pred'].values
                if len(yt) < 2:
                    continue
                rmse = float(np.sqrt(mean_squared_error(yt, yp)))
                mae = float(mean_absolute_error(yt, yp))
                # R2 peut être négatif quand la prédiction est mauvaise
                r2 = float(r2_score(yt, yp)) if np.var(yt) > 0 else 0.0

                Performance.objects.create(
                    algorithme=algo, fold=fold, horizon=h,
                    rmse=rmse, mae=mae, r2=r2, n_predictions=len(yt),
                )
                self.stdout.write(
                    f"  {algo:4s} fold={fold} h={h} : "
                    f"RMSE={rmse:6.3f}  MAE={mae:6.3f}  R2={r2:6.3f}  (n={len(yt)})"
                )

        # Récap moyenne par (algo, horizon)
        self.stdout.write(self.style.SUCCESS("\n=== Moyennes par algo x horizon ==="))
        for (algo, h), grp in df_eval.groupby(['algo', 'horizon']):
            yt = grp['y_true'].values
            yp = grp['y_pred'].values
            rmse = float(np.sqrt(mean_squared_error(yt, yp)))
            mae = float(mean_absolute_error(yt, yp))
            r2 = float(r2_score(yt, yp)) if np.var(yt) > 0 else 0.0
            self.stdout.write(
                f"  {algo:4s} h={h} : RMSE={rmse:.3f}  MAE={mae:.3f}  R2={r2:.3f}  (n={len(yt)})"
            )
