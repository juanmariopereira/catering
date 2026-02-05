from django import forms
from routes.models import Ruta


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
