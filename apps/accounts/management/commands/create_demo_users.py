"""Crée des utilisateurs de démonstration (admin + chef de district)."""
from django.core.management.base import BaseCommand

from apps.accounts.models import Utilisateur
from apps.core.models import District


class Command(BaseCommand):
    help = "Crée des comptes de démonstration (admin et chef de district)."

    def handle(self, *args, **options):
        # Administrateur
        admin, created = Utilisateur.objects.get_or_create(
            username='admin_gtr',
            defaults={
                'email': 'admin@gtr-extremenord.cm',
                'first_name': 'Administrateur',
                'last_name': 'GTR',
                'fonction': 'Coordonnateur GTR Paludisme',
                'role': Utilisateur.Role.ADMIN,
                'is_staff': True,
            }
        )
        if created:
            admin.set_password('Admin@2025')
            admin.save()
            self.stdout.write(self.style.SUCCESS(
                f"Compte admin créé : admin_gtr / Admin@2025"
            ))
        else:
            self.stdout.write("Compte admin déjà existant.")

        # Chef de district (premier district disponible)
        first_district = District.objects.first()
        if first_district:
            chef, created = Utilisateur.objects.get_or_create(
                username='chef_demo',
                defaults={
                    'email': 'chef.demo@gtr-extremenord.cm',
                    'first_name': 'Chef',
                    'last_name': first_district.nom.replace('District ', ''),
                    'fonction': "Chef d'aire de santé",
                    'role': Utilisateur.Role.CHEF,
                    'district': first_district,
                }
            )
            if created:
                chef.set_password('Chef@2025')
                chef.save()
                self.stdout.write(self.style.SUCCESS(
                    f"Compte chef créé : chef_demo / Chef@2025 (district : {first_district.nom})"
                ))
            else:
                self.stdout.write("Compte chef déjà existant.")
        else:
            self.stdout.write(self.style.WARNING(
                "Aucun district en base. Lancez d'abord 'python manage.py seed_districts'."
            ))
