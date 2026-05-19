"""Charge les seuils d'alerte et métriques de performance issus du notebook."""
import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import District, Performance, SeuilAlerte


class Command(BaseCommand):
    help = "Charge seuils_alerte.csv et metriques_walk_forward.csv depuis outputs/."

    def handle(self, *args, **options):
        outputs = settings.ML_OUTPUTS_DIR

        # ---------- Seuils d'alerte ----------
        seuils_file = outputs / 'seuils_alerte.csv'
        if seuils_file.exists():
            df = pd.read_csv(seuils_file)
            districts = {d.nom: d for d in District.objects.all()}
            nb = 0
            with transaction.atomic():
                SeuilAlerte.objects.all().delete()
                for _, row in df.iterrows():
                    d = districts.get(row['district'])
                    if d:
                        SeuilAlerte.objects.create(
                            district=d,
                            mois_calendaire=int(row['mois']),
                            p25=float(row.get('p25', 0) or 0),
                            p75=float(row['p75']),
                            p90=float(row['p90']),
                        )
                        nb += 1
            self.stdout.write(self.style.SUCCESS(f"Seuils chargés : {nb}"))
        else:
            self.stdout.write(self.style.WARNING(
                f"{seuils_file} introuvable. Skipping."
            ))

        # ---------- Performances ----------
        perf_file = outputs / 'metriques_walk_forward.csv'
        if perf_file.exists():
            df = pd.read_csv(perf_file)
            nb = 0
            with transaction.atomic():
                Performance.objects.all().delete()
                for _, row in df.iterrows():
                    algo = str(row.get('algo') or row.get('algorithme') or 'RF').upper()
                    if algo not in ('RF', 'XGB'):
                        continue
                    Performance.objects.create(
                        algorithme=algo,
                        fold=int(row['fold']),
                        horizon=int(row['horizon']),
                        rmse=float(row['rmse']),
                        mae=float(row['mae']),
                        r2=float(row['r2']),
                        n_predictions=int(row.get('n', 0)),
                    )
                    nb += 1
            self.stdout.write(self.style.SUCCESS(f"Performances chargées : {nb}"))
        else:
            self.stdout.write(self.style.WARNING(
                f"{perf_file} introuvable. Skipping."
            ))
