"""
Calcule les seuils d'alerte épidémique (P25 / P75 / P90) par district x mois calendaire
à partir de l'historique d'observations en base (méthode OMS 2014).

Pour chaque (district, mois_calendaire), on calcule les percentiles
de l'incidence observée sur toutes les années disponibles.

À lancer après seed_districts + load_initial_data, ou chaque fois que
de nouvelles observations sont importées.
"""
from collections import defaultdict

import numpy as np
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import District, Observation, SeuilAlerte


class Command(BaseCommand):
    help = ("Calcule les seuils d'alerte P25/P75/P90 par district x mois calendaire "
            "à partir des observations historiques.")

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

        # ----- Agrégation des incidences par (district_id, mois) -----
        per_key = defaultdict(list)
        for o in obs_qs:
            inc = (o.cas_confirmes / o.population) * 1000 if o.population else 0
            per_key[(o.district_id, o.mois)].append(inc)

        nb_paires = len(per_key)
        self.stdout.write(f"Paires (district × mois) à traiter : {nb_paires}")

        # ----- Calcul percentiles + écriture en base -----
        districts = {d.id: d for d in District.objects.all()}
        seuils_objs = []
        nb_skip = 0
        stats = {'rouge': 0, 'orange': 0, 'vert': 0}   # comptage indicatif

        with transaction.atomic():
            SeuilAlerte.objects.all().delete()

            for (district_id, mois), values in per_key.items():
                if len(values) < min_obs:
                    nb_skip += 1
                    continue
                arr = np.array(values, dtype=float)
                p25 = float(np.percentile(arr, 25))
                p75 = float(np.percentile(arr, 75))
                p90 = float(np.percentile(arr, 90))

                seuils_objs.append(SeuilAlerte(
                    district=districts[district_id],
                    mois_calendaire=int(mois),
                    p25=p25, p75=p75, p90=p90,
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

        # Exemple de seuils calculés
        sample = SeuilAlerte.objects.select_related('district').filter(mois_calendaire=9)[:5]
        if sample.exists():
            self.stdout.write("\nExemples (mois 9 = septembre, pic palustre attendu) :")
            for s in sample:
                self.stdout.write(
                    f"  {s.district.nom_court:20s} : P25={s.p25:6.2f}  P75={s.p75:6.2f}  P90={s.p90:6.2f}"
                )
