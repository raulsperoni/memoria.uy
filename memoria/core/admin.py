from django.contrib import admin

# Register your models here.
from .models import Noticia, Voto

admin.site.register(Noticia)
admin.site.register(Voto)
