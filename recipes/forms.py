import json
from django import forms
from django.db.models import Q
from .models import Ingrediente, Alergeno, UnidadMedida


class IngredienteForm(forms.ModelForm):
    """Alérgenos: selección múltiple desde el catálogo; se guarda como lista de nombres en JSONField."""

    class Meta:
        model = Ingrediente
        fields = ['nombre', 'unidad_medida', 'info_nutricional', 'activo']
        widgets = {
            'info_nutricional': forms.Textarea(attrs={
                'rows': 6,
                'cols': 60,
                'placeholder': '{"por_100g": {"calorias": 165, "proteinas": 31, "carbohidratos": 0, "grasas": 3.6, "fibra": 0}}',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            gramo = UnidadMedida.objects.filter(activo=True).filter(
                Q(nombre__iexact='Gramo') | Q(simbolo__iexact='gr')
            ).first()
            if gramo:
                self.initial.setdefault('unidad_medida', gramo.pk)
        self.fields['alergenos'] = forms.ModelMultipleChoiceField(
            queryset=Alergeno.objects.filter(activo=True).order_by('orden', 'nombre'),
            required=False,
            label='Alérgenos',
            help_text='Añada los alérgenos que puede contener este ingrediente desde la lista.',
            widget=forms.CheckboxSelectMultiple,
        )
        if self.instance and self.instance.pk and getattr(self.instance, 'alergenos', None):
            nombres = self.instance.alergenos
            if isinstance(nombres, list) and nombres:
                mapping = {a.nombre.lower(): a.pk for a in Alergeno.objects.filter(activo=True)}
                ids = [
                    mapping[n.strip().lower()] for n in nombres
                    if n and isinstance(n, str) and n.strip().lower() in mapping
                ]
                self.initial['alergenos'] = list(dict.fromkeys(ids))

    def clean_info_nutricional(self):
        val = self.cleaned_data.get('info_nutricional')
        if isinstance(val, str):
            try:
                val = json.loads(val) if val.strip() else {}
            except json.JSONDecodeError:
                return {}
        if isinstance(val, dict) and 'alergenos' in val:
            val = dict(val)  # copy to avoid mutating
            alerg = val.pop('alergenos', [])
            if isinstance(alerg, list):
                self.cleaned_data['alergenos'] = [
                    a for a in Alergeno.objects.filter(nombre__in=[str(x).strip() for x in alerg if x])
                ]
        return val if isinstance(val, dict) else {}

    def save(self, commit=True):
        obj = super().save(commit=False)
        sel = self.cleaned_data.get('alergenos', []) or []
        obj.alergenos = [a.nombre for a in sel]
        if commit:
            obj.save()
        return obj


class RecetaForm(forms.ModelForm):
    pass  # usado solo si necesitamos customizar; por ahora las vistas usan fields directamente
