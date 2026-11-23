def signup(request):
    """Expone si el registro está abierto, para no invitar a una página cerrada."""
    from allauth.account.adapter import get_adapter

    return {"signup_abierto": get_adapter(request).is_open_for_signup(request)}
