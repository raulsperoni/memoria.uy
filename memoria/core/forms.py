# forms.py

from django import forms

VOTE_CHOICES = [
    ("buena", "Buena noticia"),
    ("mala", "Mala noticia"),
    ("neutral", "Neutral"),
]


class NoticiaForm(forms.Form):
    opinion = forms.ChoiceField(choices=VOTE_CHOICES, label="Your Vote")
    enlace = forms.URLField(label="URL")
