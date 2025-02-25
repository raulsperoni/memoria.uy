# forms.py

from django import forms

VOTE_CHOICES = [
    ("buena", "Buena noticia"),
    ("mala", "Mala noticia"),
    ("neutral", "Neutral"),
]


class NoticiaForm(forms.Form):
    opinion = forms.ChoiceField(choices=VOTE_CHOICES, label="Your Vote")
    enlace = forms.URLField(
        label="Pega el enlace de la noticia aquí",
        widget=forms.URLInput(
            attrs={
                "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "Pega el enlace de la noticia aquí",
            }
        ),
    )
