"""
Charge les performances OFFICIELLES (issues du mémoire / notebook validé)
des modèles Random Forest et XGBoost dans la base.

Ce sont les moyennes finales par algorithme x horizon obtenues après validation
walk-forward sur 5 plis (2021-2025).
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import Performance

# Performances officielles validées (Mémoire 2025)
# Format : (algorithme, horizon, rmse, mae, r2)
PERFORMANCES_OFFICIELLES = [
    # Random Forest
    ('RF',  1, 3.23, 2.04, 0.783),
    ('RF',  2, 4.35, 2.77, 0.618),
    ('RF',  3, 5.05, 3.22, 0.506),
    # XGBoost
    ('XGB', 1, 3.21, 2.04, 0.783),
    ('XGB', 2, 4.04, 2.63, 0.665),
    ('XGB', 3, 4.54, 2.97, 0.598),
]

# Nombre de prédictions par fold (32 districts × ~10 mois testés par pli)
N_PRED_PAR_FOLD = 320


class Command(BaseCommand):
    help = ("Charge les performances officielles RF/XGB validées en walk-forward "
            "(remplace tout calcul automatique antérieur).")

    def handle(self, *args, **options):
        with transaction.atomic():
            Performance.objects.all().delete()

            for algo, h, rmse, mae, r2 in PERFORMANCES_OFFICIELLES:
                # On crée une seule entrée par (algo, horizon) avec fold=1
                # (la vue de l'app fait déjà un Avg, donc la moyenne d'une seule
                # valeur reste la même.)
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
        self.stdout.write("\nRecapitulatif :")
        self.stdout.write("  Algorithme  Horizon   RMSE    MAE     R2")
        self.stdout.write("  " + "-" * 50)
        for algo, h, rmse, mae, r2 in PERFORMANCES_OFFICIELLES:
            label = 'Random Forest' if algo == 'RF' else 'XGBoost     '
            self.stdout.write(
                f"  {label}  {h} mois    {rmse:.2f}    {mae:.2f}    {r2:.3f}"
            )
