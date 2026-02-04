# forms.py

from django import forms
from allauth.account.forms import SignupForm

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


class CustomSignupForm(SignupForm):
    """
    Custom signup form that adds alias field and preferences.
    """
    alias = forms.CharField(
        max_length=30,
        required=False,
        label="Alias (opcional)",
        help_text="Nombre que aparecerá en el mapa de opiniones",
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-4 py-3 border-2 border-black mono text-sm focus:outline-none focus:ring-2 focus:ring-black",
                "placeholder": "ej: JuanUY, MariaM, etc.",
            }
        ),
    )
    
    show_alias_on_map = forms.BooleanField(
        required=False,
        initial=True,
        label="Mostrar mi alias en el mapa de opiniones",
        widget=forms.CheckboxInput(
            attrs={
                "class": "w-4 h-4 border-2 border-black focus:ring-2 focus:ring-black",
            }
        ),
    )
    
    weekly_email_enabled = forms.BooleanField(
        required=False,
        initial=True,
        label="Recibir email semanal con nuevas noticias",
        widget=forms.CheckboxInput(
            attrs={
                "class": "w-4 h-4 border-2 border-black focus:ring-2 focus:ring-black",
            }
        ),
    )
    
    def save(self, request):
        user = super().save(request)
        
        # Get or create profile and set preferences
        from core.models import UserProfile
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.alias = self.cleaned_data.get('alias', '')
        profile.show_alias_on_map = self.cleaned_data.get('show_alias_on_map', True)
        profile.weekly_email_enabled = self.cleaned_data.get('weekly_email_enabled', True)
        profile.save()
        
        return user


class ProfileEditForm(forms.ModelForm):
    """
    Form for editing user profile (alias and preferences).
    """
    class Meta:
        from core.models import UserProfile
        model = UserProfile
        fields = ['alias', 'show_alias_on_map', 'weekly_email_enabled', 'reengagement_email_enabled']
        labels = {
            'alias': 'Alias (opcional)',
            'show_alias_on_map': 'Mostrar mi alias en el mapa de opiniones',
            'weekly_email_enabled': 'Recibir email semanal con nuevas noticias',
            'reengagement_email_enabled': 'Recibir correos cuando hace tiempo que no entrás',
        }
        help_texts = {
            'alias': 'Nombre que aparecerá en el mapa de opiniones',
        }
        widgets = {
            'alias': forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-3 border-2 border-black mono text-sm focus:outline-none focus:ring-2 focus:ring-black",
                    "placeholder": "ej: JuanUY, MariaM, etc.",
                    "maxlength": "30",
                }
            ),
            'show_alias_on_map': forms.CheckboxInput(
                attrs={
                    "class": "w-4 h-4 border-2 border-black focus:ring-2 focus:ring-black",
                }
            ),
            'weekly_email_enabled': forms.CheckboxInput(
                attrs={
                    "class": "w-4 h-4 border-2 border-black focus:ring-2 focus:ring-black",
                }
            ),
            'reengagement_email_enabled': forms.CheckboxInput(
                attrs={
                    "class": "w-4 h-4 border-2 border-black focus:ring-2 focus:ring-black",
                }
            ),
        }
