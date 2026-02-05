import json
from django import forms
from .models import Ingrediente


class IngredienteForm(forms.ModelForm):
    class Meta:
        model = Ingrediente
        fields = ['nombre', 'unidad_medida', 'info_nutricional', 'alergenos', 'activo']
        widgets = {
            'info_nutricional': forms.Textarea(attrs={
                'rows': 6,
                'cols': 60,
                'placeholder': '{"por_100g": {"calorias": 165, "proteinas": 31, "carbohidratos": 0, "grasas": 3.6, "fibra": 0}}',
            }),
            'alergenos': forms.Textarea(attrs={
                'rows': 2,
                'cols': 40,
                'placeholder': '["gluten", "lactosa"] o dejar vacío',
            }),
        }

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
                self.cleaned_data['alergenos'] = [str(a) for a in alerg if a]
        return val if isinstance(val, dict) else {}

    def clean_alergenos(self):
        val = self.cleaned_data.get('alergenos')
        if isinstance(val, str):
            try:
                val = json.loads(val) if val.strip() else []
            except json.JSONDecodeError:
                val = []
        return val if isinstance(val, list) else []

    def save(self, commit=True):
        obj = super().save(commit=False)
        if 'alergenos' in self.cleaned_data:
            obj.alergenos = self.cleaned_data.get('alergenos') or []
        if commit:
            obj.save()
        return obj


class RecetaForm(forms.ModelForm):
    pass  # usado solo si necesitamos customizar; por ahora las vistas usan fields directamente
