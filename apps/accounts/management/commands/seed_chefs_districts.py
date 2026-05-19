"""
Crée automatiquement un compte 'Chef de district' pour CHAQUE district sanitaire.

Règle d'attribution :
  - login    = nom court du district (sans 'District '), normalisé en minuscules,
               accents retirés, espaces remplacés par '_' (ex. 'maroua_1', 'kar_hay')
  - mot de passe = <login>@<année courante>  (ex. 'maroua_1@2026')

Exemples :
  District Bogo       -> user: bogo        / password: bogo@2026
  District Maroua 1   -> user: maroua_1    / password: maroua_1@2026
  District Kar Hay    -> user: kar_hay     / password: kar_hay@2026

Le compte administrateur (admin_gtr) est créé / mis à jour en parallèle.
"""
import csv
import unicodedata
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.accounts.models import Utilisateur
from apps.core.models import District


def _slugify_simple(s: str) -> str:
    """Normalise un nom de district en identifiant ASCII : 'Maroua 1' -> 'maroua_1'."""
    s = (s or '').strip().replace('District ', '')
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    s = s.lower()
    out = []
    for ch in s:
        if ch.isalnum():
            out.append(ch)
        else:
            out.append('_')
    while '__' in ''.join(out):
        out = list(''.join(out).replace('__', '_'))
    return ''.join(out).strip('_')


class Command(BaseCommand):
    help = ("Crée un compte 'Chef de district' pour chacun des 32 districts. "
            "Login = nom court normalisé, mot de passe = login@<année>.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--annee', type=int, default=date.today().year,
            help="Année à utiliser dans le mot de passe (par défaut: année courante)"
        )
        parser.add_argument(
            '--force-reset', action='store_true',
            help="Réinitialise les mots de passe des comptes existants"
        )
        parser.add_argument(
            '--export', type=str, default='comptes_chefs_districts.csv',
            help="Chemin du CSV récapitulatif (login + mot de passe en clair)"
        )

    def handle(self, *args, **options):
        annee = options['annee']
        force_reset = options['force_reset']
        export_path = Path(options['export'])
        if not export_path.is_absolute():
            export_path = settings.BASE_DIR / export_path

        districts = District.objects.all().order_by('nom')
        if not districts.exists():
            self.stderr.write(self.style.ERROR(
                "Aucun district en base. Lancez d'abord 'python manage.py seed_districts'."
            ))
            return

        # ---------- Compte administrateur ----------
        admin, created_admin = Utilisateur.objects.get_or_create(
            username='admin_gtr',
            defaults={
                'email': 'admin@delegation-extremenord.cm',
                'first_name': 'Administrateur',
                'last_name': 'GTR Paludisme',
                'fonction': "Coordonnateur GTR Paludisme — Délégation Régionale de la Santé Publique",
                'role': Utilisateur.Role.ADMIN,
                'is_staff': True,
            }
        )
        if created_admin or force_reset:
            admin_pwd = f'admin@{annee}'
            admin.set_password(admin_pwd)
            admin.save()
            admin_pwd_for_csv = admin_pwd
        else:
            admin_pwd_for_csv = '(inchangé)'

        # ---------- Chefs de district ----------
        comptes = []
        nb_created = nb_updated = nb_reset = 0

        for d in districts:
            login = _slugify_simple(d.nom)
            mot_de_passe = f'{login}@{annee}'

            user, created = Utilisateur.objects.get_or_create(
                username=login,
                defaults={
                    'email': f'{login}@delegation-extremenord.cm',
                    'first_name': 'Chef de district',
                    'last_name': d.nom_court,
                    'fonction': f"Chef d'aire de santé — {d.nom}",
                    'role': Utilisateur.Role.CHEF,
                    'district': d,
                }
            )

            if created:
                user.set_password(mot_de_passe)
                user.save()
                nb_created += 1
                pwd_csv = mot_de_passe
            else:
                # Mettre à jour le district de rattachement si nécessaire
                changed = False
                if user.district_id != d.id:
                    user.district = d
                    changed = True
                if user.role != Utilisateur.Role.CHEF:
                    user.role = Utilisateur.Role.CHEF
                    changed = True
                if force_reset:
                    user.set_password(mot_de_passe)
                    changed = True
                    nb_reset += 1
                    pwd_csv = mot_de_passe
                else:
                    pwd_csv = '(inchangé)'
                if changed:
                    user.save()
                    nb_updated += 1

            comptes.append({
                'district': d.nom,
                'login': login,
                'mot_de_passe': pwd_csv,
                'role': 'Chef de district',
            })

        # Insérer aussi l'admin en tête
        comptes_export = [
            {'district': '(tous)', 'login': 'admin_gtr',
             'mot_de_passe': admin_pwd_for_csv, 'role': 'Administrateur'}
        ] + comptes

        # ---------- Export CSV ----------
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with open(export_path, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['district', 'login', 'mot_de_passe', 'role'])
            w.writeheader()
            w.writerows(comptes_export)

        # ---------- Récapitulatif ----------
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f"=== Comptes créés / mis à jour ==="
        ))
        self.stdout.write(f"  Administrateur : admin_gtr / admin@{annee}")
        self.stdout.write(f"  Chefs de district : {nb_created} créés, {nb_updated} mis à jour, {nb_reset} mots de passe réinitialisés.")
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f"Récapitulatif exporté : {export_path}"
        ))
        self.stdout.write('')
        self.stdout.write("Exemples de comptes :")
        for c in comptes[:5]:
            self.stdout.write(f"  - {c['login']:20s} / {c['mot_de_passe']:25s}  ({c['district']})")
        if len(comptes) > 5:
            self.stdout.write(f"  ... et {len(comptes) - 5} autres (voir le CSV exporté)")
