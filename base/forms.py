"""
Formularios del proyecto base.
"""
from django import forms
from .models import Feriado, ParametroSistema


class ParametroSistemaForm(forms.ModelForm):
    """Formulario para crear o editar un parámetro del sistema."""

    class Meta:
        model = ParametroSistema
        fields = ('clave', 'valor', 'descripcion')
        widgets = {
            'clave': forms.TextInput(attrs={'placeholder': 'Ej: nombre_empresa', 'maxlength': 100}),
            'valor': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Valor del parámetro'}),
            'descripcion': forms.TextInput(attrs={'placeholder': 'Descripción opcional', 'maxlength': 255}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['clave'].disabled = True


class FeriadoForm(forms.ModelForm):
    """Formulario para crear y editar feriados."""

    class Meta:
        model = Feriado
        fields = ('fecha', 'nombre')
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 255}),
        }

    def clean_fecha(self):
        fecha = self.cleaned_data.get('fecha')
        if fecha is None:
            return fecha
        qs = Feriado.objects.filter(fecha=fecha)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Ya existe un feriado registrado para esta fecha.')
        return fecha


class LogoEmpresaForm(forms.Form):
    """Formulario para subir el logo de la empresa (archivo de imagen)."""
    logo = forms.ImageField(
        required=False,
        label="Archivo del logo",
        help_text="Imagen del logo (PNG, JPG, etc.). Se mostrará en la barra superior. Tamaño recomendado: altura ~40px.",
        widget=forms.FileInput(attrs={'accept': 'image/*', 'class': 'form-control'}),
    )
    quitar_logo = forms.BooleanField(
        required=False,
        initial=False,
        label="Quitar logo actual",
        help_text="Marque para eliminar el logo actual (no suba ningún archivo).",
    )
