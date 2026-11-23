"""Medios iniciales (docs/PLAN_2027.md §16). Feeds se detectan con
`manage.py detectar_feeds`."""

EXCLUIDAS_COMUNES = [
    "/deportes", "/deporte/", "/futbol", "/espectaculos", "/entretenimiento",
    "/farandula", "/horoscopo", "/recetas", "/gastronomia", "/tecnologia/gaming",
    "/autos", "/turismo", "/moda", "/tendencias", "/videos", "/fotogalerias",
    "/clasificados", "/necrologicas", "/quiniela", "/cinco-de-oro",
]

MEDIOS = [
    {"nombre": "El País", "slug": "el-pais", "dominio": "elpais.com.uy", "pago": True},
    {"nombre": "El Observador", "slug": "el-observador", "dominio": "elobservador.com.uy", "pago": True},
    {"nombre": "Montevideo Portal", "slug": "montevideo-portal", "dominio": "montevideo.com.uy"},
    {"nombre": "la diaria", "slug": "la-diaria", "dominio": "ladiaria.com.uy", "pago": True},
    {"nombre": "Búsqueda", "slug": "busqueda", "dominio": "busqueda.com.uy", "pago": True},
    {"nombre": "Brecha", "slug": "brecha", "dominio": "brecha.com.uy", "pago": True},
    {"nombre": "La Mañana", "slug": "la-manana", "dominio": "lamanana.uy"},
    {"nombre": "Subrayado", "slug": "subrayado", "dominio": "subrayado.com.uy"},
    {"nombre": "Telemundo", "slug": "telemundo", "dominio": "teledoce.com"},
    {"nombre": "Sudestada", "slug": "sudestada", "dominio": "sudestada.com.uy"},
    {"nombre": "Presidencia", "slug": "presidencia", "dominio": "gub.uy", "tipo": "oficial",
     "secciones_incluidas": ["/presidencia/comunicacion/"]},
    {"nombre": "Parlamento", "slug": "parlamento", "dominio": "parlamento.gub.uy", "tipo": "oficial",
     "secciones_incluidas": ["/noticiasyeventos/"]},
]
