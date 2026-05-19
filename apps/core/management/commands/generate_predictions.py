"""
Génère et stocke en base les prévisions à h=1, 2 et 3 pour tous les districts
et les 2 algorithmes (RF et XGB).

Idempotent : recalcule à partir de la dernière observation en base.
Utilise les seuils SeuilAlerte (méthode des écarts-types) pour déterminer les niveaux.
"""
import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import (District, Meteo, Observation, Prevision,
                              SeuilAlerte)
from apps.predictions.engine import predict_recursive
from apps.predictions.ml_loader import is_ready


class Command(BaseCommand):
    help = ("Génère et stocke les prévisions (32 districts × 2 algos × 3 horizons "
            "= 192 entrées) en utilisant les seuils écart-type pour les niveaux.")

    def handle(self, *args, **options):
        if not is_ready():
            self.stderr.write(self.style.ERROR(
                "Modèles ML non chargés. Vérifiez outputs/models/."
            ))
            return

        # Cache des seuils
        seuils_map = {(s.district_id, s.mois_calendaire): s
                      for s in SeuilAlerte.objects.all()}
        self.stdout.write(f"Seuils en cache : {len(seuils_map)}")

        nb_total = 0
        nb_districts_ok = 0

        with transaction.atomic():
            Prevision.objects.all().delete()

            for district in District.objects.all().order_by('nom'):
                obs = list(Observation.objects.filter(district=district).order_by('date'))
                meteos = {m.date: m for m in Meteo.objects.filter(district=district)}
                if not obs:
                    continue

                rows = []
                for o in obs:
                    m = meteos.get(o.date)
                    rows.append({
                        'date': o.date, 'annee': o.annee, 'mois': o.mois,
                        'incidence': o.incidence,
                        'precip_mensuel': m.precip_mensuel if m else 0,
                        'temp_moy': m.temp_moy if m else 0,
                        'humidite': m.humidite if m else 0,
                        'population': o.population,
                    })
                historic_df = pd.DataFrame(rows)
                derniere_date = obs[-1].date

                district_ok = False
                for algo in ['RF', 'XGB']:
                    try:
                        preds = predict_recursive(algo, district.nom, historic_df, horizons=[1, 2, 3])
                    except Exception as exc:
                        self.stdout.write(self.style.WARNING(
                            f"  {district.nom_court} / {algo} : {exc}"
                        ))
                        continue

                    for h, p in preds.items():
                        seuil = seuils_map.get((district.id, p['mois_cible']))
                        s_alerte = seuil.seuil_alerte if seuil else 0
                        s_epidemio = seuil.seuil_epidemio if seuil else 0
                        niveau = 'vert'
                        if seuil:
                            if p['incidence'] >= seuil.seuil_epidemio:
                                niveau = 'rouge'
                            elif p['incidence'] >= seuil.seuil_alerte:
                                niveau = 'orange'
                        cas = (p['incidence'] * district.population) / 1000

                        Prevision.objects.create(
                            district=district,
                            algorithme=algo,
                            horizon=h,
                            date_origine=derniere_date,
                            date_cible=p['date_cible'],
                            incidence_predite=p['incidence'],
                            cas_predits=cas,
                            niveau_alerte=niveau,
                            seuil_alerte=s_alerte,
                            seuil_epidemio=s_epidemio,
                        )
                        nb_total += 1
                        district_ok = True

                if district_ok:
                    nb_districts_ok += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nPrevisions generees : {nb_total} entrees pour {nb_districts_ok} districts."
        ))

        # Résumé par niveau (horizon 1, algo XGB par défaut)
        nb_rouge = Prevision.objects.filter(algorithme='XGB', horizon=1, niveau_alerte='rouge').count()
        nb_orange = Prevision.objects.filter(algorithme='XGB', horizon=1, niveau_alerte='orange').count()
        nb_vert = Prevision.objects.filter(algorithme='XGB', horizon=1, niveau_alerte='vert').count()
        self.stdout.write(f"\nRepartition XGB h=1 : rouge={nb_rouge}, orange={nb_orange}, vert={nb_vert}")
