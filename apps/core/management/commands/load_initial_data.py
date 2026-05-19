"""Charge les données initiales (DATA_COMP_2025_epuree.xlsx) dans la base."""
import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import District, Meteo, Observation


class Command(BaseCommand):
    help = "Charge l'historique 2017-2025 depuis DATA_COMP_2025_epuree.xlsx."

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, default=None,
                            help='Chemin du fichier Excel (par défaut: data_sources/DATA_COMP_2025_epuree.xlsx)')
        parser.add_argument('--truncate', action='store_true',
                            help='Vider Observation et Meteo avant le chargement')

    def handle(self, *args, **options):
        file_path = options['file'] or settings.INITIAL_DATA_FILE

        if not file_path or not str(file_path).startswith(str(settings.BASE_DIR)):
            file_path = settings.INITIAL_DATA_FILE

        from pathlib import Path
        file_path = Path(file_path)

        if not file_path.exists():
            self.stderr.write(self.style.ERROR(
                f"Fichier introuvable : {file_path}\n"
                f"Placez 'DATA_COMP_2025_epuree.xlsx' dans data_sources/"
            ))
            return

        self.stdout.write(f"Lecture de {file_path.name}...")
        df = pd.read_excel(file_path)
        df['date'] = pd.to_datetime(df['date']).dt.date
        self.stdout.write(f"  {len(df)} lignes lues, {df['district'].nunique()} districts")

        if options['truncate']:
            Observation.objects.all().delete()
            Meteo.objects.all().delete()
            self.stdout.write(self.style.WARNING("Tables Observation et Meteo vidées."))

        # Cache des districts
        districts = {d.nom: d for d in District.objects.all()}
        missing = set(df['district'].unique()) - set(districts.keys())
        if missing:
            self.stderr.write(self.style.ERROR(
                f"Districts absents en base : {missing}. "
                f"Lancez 'python manage.py seed_districts' d'abord."
            ))
            return

        # Insertion en bulk
        observations = []
        meteos = []
        district_pop = {}

        for _, row in df.iterrows():
            district = districts[row['district']]
            d = row['date']
            pop = int(row['population'])
            district_pop[district.id] = pop  # garder la dernière

            observations.append(Observation(
                district=district,
                date=d,
                annee=int(row['annee']),
                mois=int(row['mois']),
                trimestre=str(row.get('trimestre', '')),
                cas_confirmes=float(row['cas_confirmes']),
                population=pop,
            ))
            meteos.append(Meteo(
                district=district,
                date=d,
                temp_moy=float(row['temp_moy']),
                humidite=float(row['humidite']),
                precip_mensuel=float(row['precip_mensuel']),
                source='historique_initial',
            ))

        with transaction.atomic():
            Observation.objects.bulk_create(observations, ignore_conflicts=True, batch_size=500)
            Meteo.objects.bulk_create(meteos, ignore_conflicts=True, batch_size=500)

            # Mise à jour des populations sur District
            for d_id, pop in district_pop.items():
                District.objects.filter(id=d_id).update(population=pop)

        self.stdout.write(self.style.SUCCESS(
            f"Import terminé : {Observation.objects.count()} observations, "
            f"{Meteo.objects.count()} météo en base."
        ))
