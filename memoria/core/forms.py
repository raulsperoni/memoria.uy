# forms.py

from django import forms
from .models import Noticia


class NoticiaForm(forms.ModelForm):
    class Meta:
        model = Noticia
        # Include only the fields you want the user to input.
        fields = ["titulo", "enlace", "fecha_publicacion", "fuente", "categoria"]
