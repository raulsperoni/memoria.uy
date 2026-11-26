"""Identidad del votante: usuario autenticado o un id anónimo guardado en la
sesión. Guardamos el id en los *datos* de la sesión (no usamos session_key)
porque Django rota la session_key al hacer login y perderíamos el rastro."""

import uuid

CLAVE = "votante_anonimo"


def votante(request, crear=True) -> dict:
    """El votante del request. Con `crear=False` (los GET) nunca se toca la
    sesión: un anónimo sin id devuelve `{"session_key": None}`, que no tiene
    votos. El id nuevo se crea recién al votar, así una visita que solo lee
    no recibe cookies."""
    if request.user.is_authenticated:
        return {"usuario": request.user}
    vid = request.session.get(CLAVE)
    if not vid and not crear:
        return {"session_key": None}
    if not vid:
        vid = uuid.uuid4().hex[:32]
        request.session[CLAVE] = vid
    return {"session_key": vid}
