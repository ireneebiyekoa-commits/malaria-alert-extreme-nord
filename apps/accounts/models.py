"""
Modèle Utilisateur étendu — Système d'alerte paludisme.
Conforme au MCD du mémoire §2.3.4.3 (rôle Administrateur / Chef de district).
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class Utilisateur(AbstractUser):
    """
    Utilisateur de l'application avec rôle métier.

    - ADMIN : accès complet (KPI globaux, prévisions tous districts, import, rapports)
    - CHEF  : accès restreint à son district de rattachement uniquement
    """

    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrateur'
        CHEF = 'CHEF', 'Chef de district'

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.CHEF,
        verbose_name='Rôle',
    )
    district = models.ForeignKey(
        'core.District',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='utilisateurs',
        verbose_name='District rattaché',
        help_text="Obligatoire pour les chefs de district, vide pour les administrateurs.",
    )
    telephone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Téléphone',
    )
    fonction = models.CharField(
        max_length=120,
        blank=True,
        verbose_name='Fonction',
    )
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name='Date de création')

    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'
        ordering = ['-date_creation']

    def __str__(self):
        full = self.get_full_name() or self.username
        return f"{full} ({self.get_role_display()})"

    @property
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_chef_district(self) -> bool:
        return self.role == self.Role.CHEF and not self.is_superuser

    def peut_voir_district(self, district) -> bool:
        """Vérifie si l'utilisateur peut accéder aux données d'un district donné."""
        if self.is_admin:
            return True
        return self.district_id == district.id if district else False
