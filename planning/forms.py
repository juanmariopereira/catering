from django import forms
from django.core.exceptions import ValidationError
from .models import PlanificacionMenu, PlanificacionMenuReceta
from recipes.models import Receta


class PlanificacionMenuForm(forms.ModelForm):
    """Formulario para crear/editar menú planificado. Fecha y plan obligatorios; una sola planificación por fecha."""

    class Meta:
        model = PlanificacionMenu
        fields = ['fecha', 'plan', 'notas']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'plan': forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha'].input_formats = ['%Y-%m-%d']
        self.fields['plan'].required = True

    def clean_fecha(self):
        fecha = self.cleaned_data.get('fecha')
        if not fecha:
            return fecha
        qs = PlanificacionMenu.objects.filter(fecha=fecha)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(
                'Ya existe una planificación para esta fecha. Solo puede haber un plan por fecha.'
            )
        return fecha


class PlanificacionMenuRecetaForm(forms.ModelForm):
    """Formulario para cada fila del formset de recetas del menú. El select de receta se puebla
    por AJAX según el tipo de comida seleccionado (solo recetas de ese momento)."""

    class Meta:
        model = PlanificacionMenuReceta
        fields = ('tipo_comida', 'receta', 'orden')

    def __init__(self, *args, receta_counts=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Receta se carga por AJAX según tipo_comida; solo placeholder para no mostrar todas
        self.fields['receta'].choices = [('', '---------')]
