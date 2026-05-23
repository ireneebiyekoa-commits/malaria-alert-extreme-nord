"""
Charge les performances OFFICIELLES validées (Mémoire §3.2.5, Tableaux 3.5 et 3.9).

Périmètre d'évaluation : plis 2 à 5 de la validation walk-forward
(soit 1 536 prévisions couvrant 2022-2025). Le pli 1 est exclu car le
méta-modèle Ridge a besoin d'antécédents pour son entraînement.

Modèles évalués :
  - RF              : Random Forest récursif (modèle de base)
  - XGB             : XGBoost récursif (modèle de base)
  - META            : Méta-modèle adaptatif (recommandé en production)
                      • h=1 → Ridge stacking sur RF + XGB
                      • h=2 → XGBoost récursif (le stacking n'apporte rien à cet horizon)
                      • h=3 → XGBoost récursif (le stacking devient contre-productif)
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import Performance

# Performances officielles (Mémoire 2025, folds 2 à 5)
# Format : (algorithme, horizon, rmse, mae, r2)
PERFORMANCES_OFFICIELLES = [
    # Random Forest récursif (Tableau 3.5)
    ('RF',   1, 2.914, 1.888, 0.789),
    ('RF',   2, 4.013, 2.585, 0.617),
    ('RF',   3, 4.730, 3.038, 0.494),
    # XGBoost récursif (Tableau 3.5)
    ('XGB',  1, 2.960, 1.896, 0.781),
    ('XGB',  2, 3.821, 2.471, 0.653),
    ('XGB',  3, 4.328, 2.812, 0.577),
    # Méta-modèle ADAPTATIF (Tableau 3.9, ligne "Méta-modèle adaptatif")
    # h=1 : Ridge stacking ; h=2 et h=3 : XGBoost récursif
    ('META', 1, 2.866, 1.924, 0.795),
    ('META', 2, 3.821, 2.471, 0.653),     # = XGB
    ('META', 3, 4.328, 2.812, 0.577),     # = XGB
]

# Nombre de prévisions par pli (32 districts × ~12 mois testés)
N_PRED_PAR_FOLD = 384


class Command(BaseCommand):
    help = ("Charge les performances officielles RF / XGB / META validées en "
            "walk-forward (folds 2-5, Mémoire §3.2.5).")

    def handle(self, *args, **options):
        with transaction.atomic():
            Performance.objects.all().delete()

            for algo, h, rmse, mae, r2 in PERFORMANCES_OFFICIELLES:
                Performance.objects.create(
                    algorithme=algo,
                    fold=1,
                    horizon=h,
                    rmse=rmse,
                    mae=mae,
                    r2=r2,
                    n_predictions=N_PRED_PAR_FOLD,
                )

        self.stdout.write(self.style.SUCCESS(
            f"\nPerformances officielles chargees : {len(PERFORMANCES_OFFICIELLES)} entrees."
        ))
        self.stdout.write("\nRecapitulatif (folds 2-5, n=1536 prevs) :")
        self.stdout.write("  Algorithme    Horizon   RMSE    MAE     R2")
        self.stdout.write("  " + "-" * 52)
        labels = {'RF': 'Random Forest', 'XGB': 'XGBoost     ',
                  'META': 'META adaptat'}
        for algo, h, rmse, mae, r2 in PERFORMANCES_OFFICIELLES:
            self.stdout.write(
                f"  {labels[algo]}  {h} mois    {rmse:.3f}   {mae:.3f}   {r2:.3f}"
            )

        self.stdout.write("\nNote : META h=1 = Ridge stacking ; META h=2/3 = XGBoost (sans stacking).")
