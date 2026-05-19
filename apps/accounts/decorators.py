"""Décorateurs de permission métier."""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def admin_required(view_func):
    """Restreint l'accès aux utilisateurs administrateurs."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_admin:
            messages.error(
                request,
                "Cette page est réservée aux administrateurs."
            )
            return redirect('dashboard:index')
        return view_func(request, *args, **kwargs)
    return _wrapped
