"""Formulaires d'authentification."""
from django import forms
from django.contrib.auth.forms import AuthenticationForm


class LoginForm(AuthenticationForm):
    """Formulaire de connexion stylisé pour l'application."""

    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': "Nom d'utilisateur",
            'autocomplete': 'username',
            'autofocus': True,
        }),
        label="Identifiant",
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': "Mot de passe",
            'autocomplete': 'current-password',
        }),
        label="Mot de passe",
    )

    error_messages = {
        'invalid_login': "Identifiant ou mot de passe incorrect.",
        'inactive': "Ce compte est désactivé. Contactez l'administrateur.",
    }
