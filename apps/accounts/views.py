"""Vues d'authentification."""
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

from .forms import LoginForm


def _no_store(response):
    """Applique des en-têtes anti-cache stricts (login, logout)."""
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@never_cache
@csrf_protect
def login_view(request):
    """Vue de connexion."""
    if request.user.is_authenticated:
        return _no_store(redirect('dashboard:index'))

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            # Régénérer la session pour invalider l'ancienne (sécurité)
            request.session.cycle_key()
            messages.success(request, f"Bienvenue, {user.get_full_name() or user.username}.")
            next_url = request.POST.get('next') or request.GET.get('next')
            return _no_store(redirect(next_url or reverse('dashboard:index')))
    else:
        form = LoginForm(request)

    return _no_store(render(request, 'accounts/login.html', {'form': form}))


@never_cache
@login_required
def logout_view(request):
    """Déconnexion + invalidation totale de la session."""
    user_name = request.user.get_full_name() or request.user.username
    logout(request)
    request.session.flush()
    messages.info(request, f"Vous êtes déconnecté(e). À bientôt, {user_name}.")
    return _no_store(redirect('accueil:index'))


@login_required
def profile_view(request):
    """Page de profil utilisateur."""
    return render(request, 'accounts/profile.html', {'user': request.user})
