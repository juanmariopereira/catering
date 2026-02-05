"""
Formularios del proyecto base.
"""
from django import forms
from .models import Feriado


class FeriadoForm(forms.ModelForm):
    """Formulario para crear y editar feriados."""

    class Meta:
        model = Feriado
        fields = ('fecha', 'nombre')
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 255}),
        }
