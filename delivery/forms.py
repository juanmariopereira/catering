from django import forms
from routes.models import Ruta, PlantillaRuta
from .models import PuntoPartidaEntrega


class PuntoPartidaEntregaForm(forms.ModelForm):
    """Formulario para configurar el punto de partida (cocina/depósito) de las rutas."""

    class Meta:
        model = PuntoPartidaEntrega
        fields = ['nombre', 'direccion', 'latitud', 'longitud', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej: Cocina central'}),
            'direccion': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Dirección literal (opcional)'}),
            'latitud': forms.NumberInput(attrs={'step': 'any', 'placeholder': 'Ej: -17.783300'}),
            'longitud': forms.NumberInput(attrs={'step': 'any', 'placeholder': 'Ej: -63.182100'}),
        }


class RutaForm(forms.ModelForm):
    """Formulario de ruta con calendario para la fecha."""

    class Meta:
        model = Ruta
        fields = ['fecha', 'entregador', 'activa', 'notas']
        widgets = {
            'fecha': forms.DateInput(
                attrs={'type': 'date'},
                format='%Y-%m-%d',
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha'].input_formats = ['%Y-%m-%d']


class PlantillaRutaForm(forms.ModelForm):
    """Formulario para editar plantilla de ruta (entregador fijo)."""

    class Meta:
        model = PlantillaRuta
        fields = ['activa', 'notas']
