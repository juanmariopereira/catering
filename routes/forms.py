"""
Formularios para la app routes.
"""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from .models import Entregador

User = get_user_model()


class EntregadorForm(forms.ModelForm):
    """Formulario de entregador con creación/actualización de usuario de acceso."""
    username = forms.CharField(
        max_length=150,
        label='Usuario (inicio de sesión)',
        help_text='Nombre de usuario para que el entregador inicie sesión en la aplicación.',
        widget=forms.TextInput(attrs={'autocomplete': 'username'}),
    )
    password = forms.CharField(
        label='Contraseña',
        required=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text='En edición: dejar en blanco para no cambiar la contraseña.',
    )
    password_confirm = forms.CharField(
        label='Confirmar contraseña',
        required=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    class Meta:
        model = Entregador
        fields = ['nombre', 'telefono', 'vehiculo', 'activo', 'notas']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_edit = self.instance and self.instance.pk
        if self._is_edit and self.instance.user_id:
            self.fields['username'].initial = self.instance.user.username
            self.fields['username'].disabled = True
            self.fields['username'].help_text = 'Usuario de inicio de sesión del entregador (no se puede cambiar aquí).'
        elif not self._is_edit:
            self.fields['password'].required = True
            self.fields['password'].help_text = 'Contraseña para que el entregador inicie sesión.'
            self.fields['password_confirm'].required = True

    def clean_username(self):
        # Si el campo está disabled (edición), no viene en POST; usamos el valor actual
        if self.fields['username'].disabled:
            return self.instance.user.username if (self.instance and self.instance.user_id) else None
        username = self.cleaned_data.get('username')
        if not username:
            return username
        username = username.strip()
        if not username:
            raise forms.ValidationError('El usuario es obligatorio.')
        qs = User.objects.filter(username__iexact=username)
        if self.instance and self.instance.pk and self.instance.user_id:
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError('Ya existe un usuario con ese nombre.')
        return username

    def clean(self):
        data = super().clean()
        if self._is_edit:
            if data.get('password') or data.get('password_confirm'):
                if data.get('password') != data.get('password_confirm'):
                    self.add_error('password_confirm', 'Las contraseñas no coinciden.')
                elif data.get('password'):
                    try:
                        validate_password(data['password'])
                    except forms.ValidationError as e:
                        self.add_error('password', e)
        else:
            password = data.get('password')
            password_confirm = data.get('password_confirm')
            if password != password_confirm:
                self.add_error('password_confirm', 'Las contraseñas no coinciden.')
            if password:
                try:
                    validate_password(password)
                except forms.ValidationError as e:
                    self.add_error('password', e)
        return data
