"""Initialise les 32 districts sanitaires de l'Extrême-Nord."""
import json

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.core.models import District


class Command(BaseCommand):
    help = "Charge les 32 districts (coordonnées + correspondance GeoJSON)."

    def handle(self, *args, **options):
        coords_file = settings.DISTRICTS_COORDS_FILE
        geojson_file = settings.DISTRICTS_GEOJSON_FILE

        if not coords_file.exists():
            self.stderr.write(self.style.ERROR(
                f"Fichier de coordonnées introuvable : {coords_file}\n"
                f"Placez 'coordonnees_districts_extreme_nord.xlsx' dans data_sources/"
            ))
            return

        # Chargement des coordonnées
        coords = pd.read_excel(coords_file)
        self.stdout.write(f"Coordonnées chargées : {len(coords)} districts")

        # Chargement du GeoJSON pour récupérer les district_id
        geojson_map = {}
        if geojson_file.exists():
            with open(geojson_file, 'r', encoding='utf-8') as f:
                geo = json.load(f)
            for feat in geo.get('features', []):
                props = feat.get('properties', {})
                nom = props.get('district_nom')
                gid = props.get('district_id')
                if nom and gid:
                    geojson_map[nom] = gid
            self.stdout.write(f"GeoJSON chargé : {len(geojson_map)} correspondances")

        # Insertion / mise à jour
        nb_created = 0
        nb_updated = 0
        for _, row in coords.iterrows():
            nom = str(row['district_name']).strip()
            obj, created = District.objects.update_or_create(
                nom=nom,
                defaults={
                    'longitude': float(row['longitude']),
                    'latitude': float(row['latitude']),
                    'code_geojson': geojson_map.get(nom, ''),
                }
            )
            if created:
                nb_created += 1
            else:
                nb_updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Districts : {nb_created} créés, {nb_updated} mis à jour. "
            f"Total en base : {District.objects.count()}"
        ))
