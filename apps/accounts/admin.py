from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display = ('username', 'get_full_name', 'email', 'role', 'district',
                    'is_active', 'date_creation')
    list_filter = ('role', 'is_active', 'district')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('-date_creation',)

    fieldsets = UserAdmin.fieldsets + (
        (_('Informations métier'), {
            'fields': ('role', 'district', 'telephone', 'fonction'),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (_('Informations métier'), {
            'fields': ('email', 'first_name', 'last_name', 'role', 'district',
                       'telephone', 'fonction'),
        }),
    )
