from django.conf import settings

from allauth.account.adapter import DefaultAccountAdapter


class CustomAccountAdapter(DefaultAccountAdapter):
    # Voseo, como el resto del sitio (la traducción de allauth usa usted).
    error_messages = {
        **DefaultAccountAdapter.error_messages,
        "email_password_mismatch": "El email o la contraseña no son correctos.",
        "username_password_mismatch": "El usuario o la contraseña no son correctos.",
        "account_inactive": "Esta cuenta está desactivada.",
        "too_many_login_attempts": "Demasiados intentos. Esperá unos minutos y probá de nuevo.",
    }

    def is_open_for_signup(self, request):
        """
        Whether to allow sign ups.
        """
        allow_signups = super(CustomAccountAdapter, self).is_open_for_signup(request)
        # Override with setting, otherwise default to super.
        return getattr(settings, "ACCOUNT_ALLOW_SIGNUPS", allow_signups)
