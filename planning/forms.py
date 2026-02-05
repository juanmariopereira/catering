from django import forms
from .models import PlanificacionMenu, PlanificacionMenuReceta
from recipes.models import Receta


class PlanificacionMenuForm(forms.ModelForm):
    """Formulario para crear/editar menú planificado. Fecha con input tipo calendario."""

    class Meta:
        model = PlanificacionMenu
        fields = ['fecha', 'plan', 'notas']
        widgets = {
            # type='date' requiere valor en YYYY-MM-DD para que se muestre al editar
            'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha'].input_formats = ['%Y-%m-%d']


class PlanificacionMenuRecetaForm(forms.ModelForm):
    """Formulario para cada fila del formset de recetas del menú. Muestra en el select de receta
    la cantidad de clientes a los que no les gusta al menos un ingrediente [N]."""

    class Meta:
        model = PlanificacionMenuReceta
        fields = ('tipo_comida', 'receta', 'orden')

    def __init__(self, *args, receta_counts=None, **kwargs):
        super().__init__(*args, **kwargs)
        if receta_counts is not None:
            recetas = Receta.objects.filter(activa=True).order_by('nombre')
            choices = [('', '---------')]
            for r in recetas:
                count = receta_counts.get(r.id, 0)
                label = f'{r.nombre} [{count}]' if count else r.nombre
                choices.append((r.id, label))
            self.fields['receta'].choices = choices
