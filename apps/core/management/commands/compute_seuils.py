"""
Calcule les seuils d'alerte épidémique par district x mois calendaire,
selon la méthode des écarts-types (recommandée par l'OMS).

Pour chaque (district, mois_calendaire) :
   Moyenne     = moyenne de l'incidence historique
   Écart-type  = écart-type de l'incidence historique
   Seuil d'alerte         = Moyenne + 1 * Écart-type
   Seuil épidémiologique  = Moyenne + 2 * Écart-type

Logique des niveaux :
   VERT    : incidence prédite < seuil_alerte
   ORANGE  : seuil_alerte ≤ incidence prédite < seuil_epidemio
   ROUGE   : incidence prédite ≥ seuil_epidemio

À lancer après seed_districts + load_initial_data, ou chaque fois que
de nouvelles observations sont importées.
"""
from collections import defaultdict

import numpy as np
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import District, Observation, SeuilAlerte


class Command(BaseCommand):
    help = ("Calcule les seuils d'alerte (Moyenne + σ) et épidémiologiques (Moyenne + 2σ) "
            "par district x mois calendaire à partir des observations historiques.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--annee-max', type=int, default=None,
            help="N'utiliser que les observations jusqu'à cette année incluse (par défaut: toutes)"
        )
        parser.add_argument(
            '--min-obs', type=int, default=3,
            help="Nombre minimum d'observations pour calculer les seuils (par défaut: 3)"
        )

    def handle(self, *args, **options):
        annee_max = options['annee_max']
        min_obs = options['min_obs']

        obs_qs = Observation.objects.select_related('district').all()
        if annee_max:
            obs_qs = obs_qs.filter(annee__lte=annee_max)
            self.stdout.write(f"Filtrage : observations jusqu'à {annee_max} incluses")

        # ----- Agrégation incidences par (district_id, mois) -----
        per_key = defaultdict(list)
        for o in obs_qs:
            inc = (o.cas_confirmes / o.population) * 1000 if o.population else 0
            per_key[(o.district_id, o.mois)].append(inc)

        nb_paires = len(per_key)
        self.stdout.write(f"Paires (district × mois) à traiter : {nb_paires}")

        # ----- Calcul moyenne + écart-type + seuils -----
        districts = {d.id: d for d in District.objects.all()}
        seuils_objs = []
        nb_skip = 0

        with transaction.atomic():
            SeuilAlerte.objects.all().delete()

            for (district_id, mois), values in per_key.items():
                if len(values) < min_obs:
                    nb_skip += 1
                    continue
                arr = np.array(values, dtype=float)
                mu = float(np.mean(arr))
                sigma = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0

                seuil_alerte = mu + 1.0 * sigma
                seuil_epidemio = mu + 2.0 * sigma

                seuils_objs.append(SeuilAlerte(
                    district=districts[district_id],
                    mois_calendaire=int(mois),
                    moyenne=round(mu, 4),
                    ecart_type=round(sigma, 4),
                    seuil_alerte=round(seuil_alerte, 4),
                    seuil_epidemio=round(seuil_epidemio, 4),
                    # Champs legacy : on les remplit aussi pour rétro-compat éventuelle
                    p75=round(seuil_alerte, 4),
                    p90=round(seuil_epidemio, 4),
                ))

            SeuilAlerte.objects.bulk_create(seuils_objs, batch_size=500)

        # ----- Récapitulatif -----
        self.stdout.write(self.style.SUCCESS(
            f"\nSeuils calculés : {len(seuils_objs)} entrées (sur {nb_paires} paires possibles)."
        ))
        if nb_skip:
            self.stdout.write(self.style.WARNING(
                f"  {nb_skip} paires ignorées (moins de {min_obs} observations)."
            ))

        sample = SeuilAlerte.objects.select_related('district').filter(mois_calendaire=9)[:5]
        if sample.exists():
            self.stdout.write("\nExemples (mois 9 = septembre, pic palustre attendu) :")
            self.stdout.write(f"  {'District':<22s} {'Moyenne':>9s} {'Σ':>7s} {'Alerte (M+σ)':>15s} {'Épidémio (M+2σ)':>18s}")
            for s in sample:
                self.stdout.write(
                    f"  {s.district.nom_court:<22s} {s.moyenne:>9.2f} {s.ecart_type:>7.2f} "
                    f"{s.seuil_alerte:>15.2f} {s.seuil_epidemio:>18.2f}"
                )
