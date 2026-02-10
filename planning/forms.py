from django import forms
from django.core.exceptions import ValidationError
from .models import PlanificacionMenu, PlanificacionMenuReceta
from recipes.models import Receta


class PlanificacionMenuForm(forms.ModelForm):
    """Formulario para crear/editar menú planificado. Una sola planificación por (fecha, plan)."""

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

    def clean(self):
        cleaned_data = super().clean()
        fecha = cleaned_data.get('fecha')
        plan = cleaned_data.get('plan')
        if not fecha or not plan:
            return cleaned_data
        qs = PlanificacionMenu.objects.filter(fecha=fecha, plan=plan)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(
                'Ya existe una planificación para esta fecha y este plan. Solo puede haber una por (fecha, plan).'
            )
        return cleaned_data


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
