from django import forms

from .models import Contrato


# Días laborables por defecto (lunes a viernes)
DIAS_ENTREGA_DEFAULT = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes']


class ContratoForm(forms.ModelForm):
    """Formulario de contrato con días de entrega como selección múltiple."""

    dias_entrega = forms.MultipleChoiceField(
        choices=Contrato.DIA_SEMANA_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Días de entrega",
        help_text="Seleccione los días en que se entrega el servicio. Por defecto: lunes a viernes.",
    )

    class Meta:
        model = Contrato
        fields = [
            'cliente', 'plan', 'fecha_inicio', 'fecha_fin', 'precio', 'frecuencia_pago',
            'direccion_entrega', 'link_maps', 'horario_entrega', 'dias_entrega', 'notas_entregador',
            'estado', 'notas',
        ]
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'fecha_fin': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'horario_entrega': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha_inicio'].input_formats = ['%Y-%m-%d']
        self.fields['fecha_fin'].input_formats = ['%Y-%m-%d']
        self.fields['horario_entrega'].input_formats = ['%H:%M', '%H:%M:%S']
        if self.instance and self.instance.pk:
            if self.instance.dias_entrega:
                self.fields['dias_entrega'].initial = self.instance.dias_entrega
        else:
            self.fields['dias_entrega'].initial = DIAS_ENTREGA_DEFAULT
            self.fields['fecha_inicio'].initial = None  # Vacía por defecto al crear
