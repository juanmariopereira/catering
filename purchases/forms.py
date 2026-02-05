from django import forms
from .models import PrevisionCompra


class PrevisionCompraForm(forms.ModelForm):
    """Formulario para crear/editar previsión de compra con inputs de fecha tipo date."""

    class Meta:
        model = PrevisionCompra
        fields = ['fecha_desde', 'fecha_hasta', 'notas']
        widgets = {
            'fecha_desde': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'fecha_hasta': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha_desde'].input_formats = ['%Y-%m-%d']
        self.fields['fecha_hasta'].input_formats = ['%Y-%m-%d']
