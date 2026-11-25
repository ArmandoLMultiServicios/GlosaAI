"""Formularios de la administración de usuarios."""

from django import forms
from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from django.contrib.auth.models import User

AYUDA_ADMINISTRADOR = 'Puede entrar a Usuarios y dar de alta o modificar cuentas.'


def _correo_por_defecto(usuario):
    return f'{usuario.lower()}@{settings.CORREO_DOMINIO}'


class FormularioNuevoUsuario(UserCreationForm):
    administrador = forms.BooleanField(label='Administrador', required=False, help_text=AYUDA_ADMINISTRADOR)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Usuario'
        self.fields['username'].help_text = (
            f'El mismo que su correo, p. ej. armandol para armandol@{settings.CORREO_DOMINIO}.')
        self.fields['email'].label = 'Correo'
        self.fields['email'].help_text = f'Si lo dejas vacío se usa usuario@{settings.CORREO_DOMINIO}.'
        self.fields['password1'].label = 'Contraseña temporal'
        self.fields['password1'].help_text = ('Al entrar por primera vez se le pedirá elegir su propia contraseña. '
                                              'Mínimo 4 caracteres.')

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if not usuario.email:
            usuario.email = _correo_por_defecto(usuario.username)
        usuario.is_staff = usuario.is_superuser = self.cleaned_data['administrador']
        if commit:
            usuario.save()
        return usuario


class FormularioEditarUsuario(forms.ModelForm):
    """Datos, acceso y (opcional) nueva contraseña de un usuario existente."""

    administrador = forms.BooleanField(label='Administrador', required=False, help_text=AYUDA_ADMINISTRADOR)
    nueva_contrasena = forms.CharField(
        label='Nueva contraseña', required=False, strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text='Déjala vacía para no cambiarla. Será temporal: al entrar se le pedirá elegir la suya.')
    confirmar_contrasena = forms.CharField(
        label='Confirmar contraseña', required=False, strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'is_active')
        labels = {'email': 'Correo', 'is_active': 'Activo'}
        help_texts = {'is_active': 'Desmárcalo para quitarle el acceso sin borrar la cuenta.'}

    def __init__(self, *args, editor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['administrador'].initial = self.instance.is_superuser
        self.es_el_mismo = editor is not None and editor.pk == self.instance.pk
        if self.es_el_mismo:
            self.fields['nueva_contrasena'].help_text = 'Déjala vacía para no cambiarla.'
            # Nadie puede quitarse a sí mismo el acceso ni el rol de administrador.
            for campo in ('is_active', 'administrador'):
                self.fields[campo].disabled = True
                self.fields[campo].help_text = 'No puedes cambiarlo en tu propia cuenta.'
            self.fields['is_active'].initial = True

    def clean(self):
        datos = super().clean()
        nueva, confirmar = datos.get('nueva_contrasena'), datos.get('confirmar_contrasena')
        if nueva or confirmar:
            if nueva != confirmar:
                self.add_error('confirmar_contrasena', 'Las contraseñas no coinciden.')
            else:
                try:
                    password_validation.validate_password(nueva, self.instance)
                except forms.ValidationError as e:
                    self.add_error('nueva_contrasena', e)
        return datos

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if not usuario.email:
            usuario.email = _correo_por_defecto(usuario.username)
        if self.es_el_mismo:
            usuario.is_active = usuario.is_superuser = True
        else:
            usuario.is_superuser = self.cleaned_data['administrador']
        usuario.is_staff = usuario.is_superuser
        if self.cleaned_data.get('nueva_contrasena'):
            usuario.set_password(self.cleaned_data['nueva_contrasena'])
        if commit:
            usuario.save()
        return usuario


class FormularioCambioContrasena(PasswordChangeForm):
    """Cambio de la propia contraseña; la nueva no puede ser igual a la actual (p. ej. la temporal)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].label = 'Contraseña actual'
        self.fields['old_password'].help_text = 'Si es tu primer ingreso, la contraseña temporal que te dieron.'

    def clean(self):
        datos = super().clean()
        nueva = datos.get('new_password1')
        if nueva and nueva == datos.get('old_password') and 'new_password1' not in self.errors:
            self.add_error('new_password1', 'La contraseña nueva debe ser distinta de la actual.')
        return datos
