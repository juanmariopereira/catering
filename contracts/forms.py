import calendar
from datetime import date, timedelta

from django import forms

from .models import Contrato, PausaContrato, ExtensionVigencia


# Días laborables por defecto (lunes a viernes)
DIAS_ENTREGA_DEFAULT = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes']


def calcular_fecha_fin_segun_frecuencia(fecha_inicio, frecuencia_pago):
    """
    Calcula la fecha de fin del contrato a partir de la fecha de inicio
    y la frecuencia de pago (un periodo según la frecuencia).
    - diario: 30 días (un mes de servicio diario)
    - semanal: 7 días (una semana)
    - quincenal: 15 días (una quincena)
    - mensual: 1 mes natural (mismo día del mes siguiente - 1 día)
    """
    if not fecha_inicio or not frecuencia_pago:
        return None
    if frecuencia_pago == 'diario':
        return fecha_inicio + timedelta(days=30)
    if frecuencia_pago == 'semanal':
        return fecha_inicio + timedelta(days=6)  # 7 días inclusive
    if frecuencia_pago == 'quincenal':
        return fecha_inicio + timedelta(days=14)  # 15 días inclusive
    if frecuencia_pago == 'mensual':
        next_month = (fecha_inicio.month % 12) + 1
        next_year = fecha_inicio.year + (fecha_inicio.month // 12)
        try:
            siguiente = date(next_year, next_month, fecha_inicio.day)
        except ValueError:
            _, last = calendar.monthrange(next_year, next_month)
            siguiente = date(next_year, next_month, min(fecha_inicio.day, last))
        return siguiente - timedelta(days=1)  # último día del periodo
    return None


class PausaContratoForm(forms.ModelForm):
    """Formulario de pausa con inputs de tipo fecha (calendario)."""
    class Meta:
        model = PausaContrato
        fields = ['fecha_inicio', 'fecha_fin', 'motivo']
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'fecha_fin': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha_inicio'].input_formats = ['%Y-%m-%d']
        self.fields['fecha_fin'].input_formats = ['%Y-%m-%d']


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
            'direccion_entrega', 'link_maps', 'horario_entrega', 'dias_entrega', 'no_incluye_delivery',
            'notas_entregador', 'notas',
        ]
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'fecha_fin': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'horario_entrega': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
        }
        help_texts = {
            'fecha_fin': 'Se calcula automáticamente según la fecha de inicio y la frecuencia de pago (un periodo). Puede modificarla manualmente si lo desea.',
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
            self.fields['frecuencia_pago'].initial = 'mensual'

    def clean(self):
        cleaned = super().clean()
        fecha_inicio = cleaned.get('fecha_inicio')
        frecuencia_pago = cleaned.get('frecuencia_pago')
        if fecha_inicio and frecuencia_pago:
            fecha_fin = calcular_fecha_fin_segun_frecuencia(fecha_inicio, frecuencia_pago)
            if fecha_fin:
                cleaned['fecha_fin'] = fecha_fin
        return cleaned


class DiasExtraForm(forms.ModelForm):
    """Formulario para dar días extra de catering (extender vigencia del contrato y cobro)."""
    class Meta:
        model = ExtensionVigencia
        fields = ['dias_agregados', 'motivo']
        widgets = {
            'dias_agregados': forms.NumberInput(attrs={'min': 1, 'max': 365, 'placeholder': 'Ej. 7'}),
            'motivo': forms.TextInput(attrs={'placeholder': 'Ej. cortesía, compensación por demora...'}),
        }
        help_texts = {
            'dias_agregados': 'Número de días que se agregan a la vigencia del contrato y al último cobro.',
            'motivo': 'Razón de la extensión (obligatorio para registro).',
        }

    def clean_dias_agregados(self):
        val = self.cleaned_data.get('dias_agregados')
        if val is not None and (val < 1 or val > 365):
            raise forms.ValidationError('Debe ser entre 1 y 365 días.')
        return val
