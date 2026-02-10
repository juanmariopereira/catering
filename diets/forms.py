"""
Formularios para la app diets.
"""
from django import forms
from .models import TipoComida, DietaReceta


class TipoComidaForm(forms.ModelForm):
    """Formulario para crear y editar tipos de comida (momentos del día)."""

    class Meta:
        model = TipoComida
        fields = ('nombre', 'orden', 'descripcion')
        widgets = {
            'nombre': forms.TextInput(attrs={'maxlength': 80, 'placeholder': 'Ej: Desayuno, Media mañana'}),
            'orden': forms.NumberInput(attrs={'min': 1, 'step': 1}),
            'descripcion': forms.Textarea(attrs={'rows': 2, 'maxlength': 200, 'placeholder': 'Opcional'}),
        }

    def clean_orden(self):
        valor = self.cleaned_data.get('orden')
        if valor is not None and valor < 1:
            raise forms.ValidationError('El orden debe ser al menos 1.')
        return valor


class DietaRecetaForm(forms.ModelForm):
    """Formulario para una receta de la dieta; tipo_comida ordenado por campo orden."""

    class Meta:
        model = DietaReceta
        fields = ['tipo_comida', 'receta', 'orden']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo_comida'].queryset = TipoComida.objects.order_by('orden', 'nombre')
