"""
Utilidad para registrar acciones de usuarios (auditoría).
Las vistas que usan LogUserActionMixin registran crear/editar/eliminar automáticamente.
"""
from base.models import UserActionLog


def log_user_action(
    request,
    accion,
    modelo,
    obj=None,
    object_id=None,
    objeto_repr=None,
    descripcion='',
    cambios=None,
):
    """
    Registra una acción de usuario en el historial.

    Args:
        request: HttpRequest (se usa request.user).
        accion: 'crear' | 'editar' | 'eliminar'.
        modelo: Nombre del tipo de registro (ej. "Feriado", "Contrato").
        obj: Instancia del modelo (opcional); se usan pk y str(obj) si no se pasan object_id/objeto_repr.
        object_id: ID del objeto (opcional si se pasa obj).
        objeto_repr: Descripción corta del objeto (opcional si se pasa obj).
        descripcion: Texto adicional opcional.
        cambios: Lista de dicts {"campo", "valor_anterior", "valor_nuevo"} para ediciones.
    """
    user = getattr(request, 'user', None) if request else None
    if user and not user.is_authenticated:
        user = None
    if obj is not None:
        if object_id is None:
            object_id = getattr(obj, 'pk', None)
        if objeto_repr is None:
            objeto_repr = str(obj)[:255]
    try:
        UserActionLog.objects.create(
            usuario=user,
            accion=accion,
            modelo=modelo,
            objeto_id=object_id,
            objeto_repr=(objeto_repr or '')[:255],
            descripcion=(descripcion or '')[:2000],
            cambios=cambios or [],
        )
    except Exception:
        pass  # No fallar la petición si falla el log


def get_changes_for_form(instance, form):
    """
    Construye la lista de cambios comparando el objeto actual con form.cleaned_data.
    Útil para ediciones: pasar el objeto antes de guardar y el formulario.
    """
    changes = []
    for field_name in form.cleaned_data:
        if not hasattr(instance, field_name):
            continue
        old_val = getattr(instance, field_name, None)
        new_val = form.cleaned_data.get(field_name)
        if old_val != new_val:
            changes.append({
                'campo': field_name,
                'valor_anterior': str(old_val) if old_val is not None else '',
                'valor_nuevo': str(new_val) if new_val is not None else '',
            })
    return changes


class LogUserActionMixin:
    """
    Mixin para vistas basadas en clases que registra crear/editar/eliminar
    en UserActionLog. Asignar a la vista (ej. LogUserActionMixin, LoginRequiredMixin, CreateView).
    """
    def get_model_label(self):
        """Nombre del modelo para el log (por defecto verbose_name o nombre de la clase)."""
        if hasattr(self, 'model') and self.model is not None:
            try:
                return self.model._meta.verbose_name.capitalize()
            except Exception:
                return self.model.__name__
        return 'Registro'

    def form_valid(self, form):
        from django.views.generic.edit import CreateView, UpdateView, DeleteView

        is_delete = isinstance(self, DeleteView)
        is_update = isinstance(self, UpdateView) and getattr(self, 'object', None) and getattr(self.object, 'pk', None)
        old_values = None
        if is_update and self.object:
            old_values = {k: getattr(self.object, k, None) for k in form.cleaned_data if hasattr(self.object, k)}
        # DeleteView: guardar objeto antes de que super().form_valid() lo borre
        _repr, _pk = '', None
        if is_delete:
            try:
                _obj = self.get_object()
                _repr = str(_obj)[:255]
                _pk = getattr(_obj, 'pk', None)
            except Exception:
                pass

        response = super().form_valid(form)

        if is_delete:
            log_user_action(self.request, 'eliminar', self.get_model_label(), object_id=_pk, objeto_repr=_repr)
            return response
        if is_update and old_values is not None:
            changes = []
            for k in form.cleaned_data:
                if k not in old_values:
                    continue
                ov, nv = old_values.get(k), form.cleaned_data.get(k)
                if ov != nv:
                    changes.append({
                        'campo': k,
                        'valor_anterior': str(ov) if ov is not None else '',
                        'valor_nuevo': str(nv) if nv is not None else '',
                    })
            log_user_action(self.request, 'editar', self.get_model_label(), obj=self.object, cambios=changes)
        else:
            log_user_action(self.request, 'crear', self.get_model_label(), obj=self.object)
        return response

    def delete(self, request, *args, **kwargs):
        from django.views.generic.edit import DeleteView

        self.object = self.get_object()
        obj_repr = str(self.object)[:255]
        obj_id = getattr(self.object, 'pk', None)
        response = super().delete(request, *args, **kwargs)
        log_user_action(
            self.request,
            'eliminar',
            self.get_model_label(),
            object_id=obj_id,
            objeto_repr=obj_repr,
        )
        return response
