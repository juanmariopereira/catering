"""
Lógica de negocio para ingredientes: crear ingrediente (validación + persistencia).
"""

from recipes.models import Ingrediente, UnidadMedida


def crear_ingrediente(nombre, unidad_medida_id):
    """
    Crea un ingrediente con nombre y unidad de medida.
    Valida y devuelve la instancia creada (o la existente si hay race condition).

    Raises:
        ValueError: si nombre vacío, unidad inválida o ya existe ingrediente con ese nombre.
    """
    nombre = (nombre or '').strip()
    if not nombre:
        raise ValueError('El nombre del ingrediente es obligatorio.')
    if not unidad_medida_id:
        raise ValueError('Seleccione la unidad de medida.')
    try:
        unidad = UnidadMedida.objects.get(pk=unidad_medida_id)
    except (UnidadMedida.DoesNotExist, ValueError, TypeError):
        raise ValueError('Unidad de medida inválida.')
    existente = Ingrediente.objects.filter(nombre__iexact=nombre).first()
    if existente:
        raise ValueError(f'Ya existe un ingrediente con el nombre "{nombre}".')
    ingrediente = Ingrediente.objects.create(
        nombre=nombre,
        unidad_medida=unidad,
        info_nutricional={},
        alergenos=[],
        activo=True,
    )
    return ingrediente


def get_ingrediente_existente_por_nombre(nombre):
    """Devuelve el ingrediente con ese nombre (case-insensitive) o None."""
    nombre = (nombre or '').strip()
    if not nombre:
        return None
    return Ingrediente.objects.filter(nombre__iexact=nombre).first()


def list_ingredientes_queryset(*, busqueda=None, activo=None):
    """Queryset de ingredientes filtrado por búsqueda y estado activo."""
    qs = Ingrediente.objects.all()
    if busqueda:
        qs = qs.filter(nombre__icontains=busqueda)
    if activo is not None and activo != '':
        qs = qs.filter(activo=activo == '1')
    return qs.order_by('nombre')


def get_unidad_medida_nombre_para_ia(unidad_medida_id):
    """
    Devuelve el nombre/símbolo de la unidad para usar en IA (estimar nutrición).
    Raises ValueError si la unidad no existe.
    """
    try:
        unidad = UnidadMedida.objects.get(pk=unidad_medida_id)
    except (UnidadMedida.DoesNotExist, ValueError, TypeError):
        raise ValueError('Unidad de medida inválida.')
    return unidad.simbolo or unidad.nombre or 'unidad'


def get_unidad_medida_unidad_ids():
    """IDs de UnidadMedida que representan 'unidad' (para equivalencia por unidad)."""
    from django.db.models import Q
    return list(
        UnidadMedida.objects.filter(
            Q(nombre__iexact='Unidad')
            | Q(nombre__iexact='Unidades')
            | Q(nombre__icontains='unidad')
            | Q(simbolo__iexact='un')
            | Q(simbolo__iendswith='un')
        ).values_list('pk', flat=True)
    )
