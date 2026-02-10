"""
Formularios del proyecto base.
"""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from .models import Feriado, ParametroSistema

User = get_user_model()


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


class UserForm(forms.ModelForm):
    """Formulario para crear y editar usuarios (fuera del admin)."""
    password = forms.CharField(
        label='Contraseña',
        required=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text='En edición: dejar en blanco para no cambiar.',
    )
    password_confirm = forms.CharField(
        label='Confirmar contraseña',
        required=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'is_staff', 'is_active', 'groups')
        labels = {
            'groups': 'Perfiles (grupos)',
        }
        widgets = {
            'username': forms.TextInput(attrs={'autocomplete': 'username'}),
            'email': forms.EmailInput(attrs={'autocomplete': 'email'}),
            'groups': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_edit = self.instance and self.instance.pk
        if self._is_edit:
            self.fields['username'].disabled = True
            self.fields['username'].help_text = 'No se puede cambiar el nombre de usuario.'
        else:
            self.fields['password'].required = True
            self.fields['password_confirm'].required = True

    def clean_username(self):
        if self.fields['username'].disabled:
            return self.instance.username if (self.instance and self.instance.pk) else ''
        username = (self.cleaned_data.get('username') or '').strip()
        if not username:
            raise forms.ValidationError('El usuario es obligatorio.')
        qs = User.objects.filter(username__iexact=username)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Ya existe un usuario con ese nombre.')
        return username

    def clean(self):
        data = super().clean()
        password = data.get('password')
        password_confirm = data.get('password_confirm')
        if password or password_confirm:
            if password != password_confirm:
                self.add_error('password_confirm', 'Las contraseñas no coinciden.')
            elif password and not self._is_edit:
                try:
                    validate_password(password)
                except forms.ValidationError as e:
                    self.add_error('password', e)
            elif password and self._is_edit:
                try:
                    validate_password(password)
                except forms.ValidationError as e:
                    self.add_error('password', e)
        elif not self._is_edit and not password:
            self.add_error('password', 'La contraseña es obligatoria al crear el usuario.')
        return data
