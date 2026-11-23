"""Identidad del votante: usuario autenticado o un id anónimo guardado en la
sesión. Guardamos el id en los *datos* de la sesión (no usamos session_key)
porque Django rota la session_key al hacer login y perderíamos el rastro."""

import uuid

CLAVE = "votante_anonimo"


def votante(request) -> dict:
    if request.user.is_authenticated:
        return {"usuario": request.user}
    vid = request.session.get(CLAVE)
    if not vid:
        vid = uuid.uuid4().hex[:32]
        request.session[CLAVE] = vid
    return {"session_key": vid}
