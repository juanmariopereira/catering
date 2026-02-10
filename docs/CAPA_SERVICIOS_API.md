# Capa de servicios y uso desde API REST

La lógica de negocio se ha movido a una **capa de servicios** por app, de forma que pueda ser reutilizada tanto por las vistas web actuales como por futuras **API views** (p. ej. para una app móvil).

## Estructura

Cada app que tiene lógica reutilizable dispone de un paquete `services/`:

- **clients/services**: `list_clientes_queryset()`, `get_cliente_detalle_data()`, `get_cliente_delete_context()`
- **contracts/services**: `list_contratos_queryset()`, `get_contrato_detalle_data()`, `aplicar_dias_extra()`, helpers de ordenación
- **planning/services**: `get_resumen_por_fecha()`, `get_clientes_reciben_fecha()`, `get_contratos_sin_entregador_fecha()`, `get_calendario_data()`
- **recipes/services**: `planificaciones_que_incluyen_receta()`, `duplicar_receta()`, `crear_ingrediente()`

Los servicios:

- Reciben parámetros simples (IDs, fechas, filtros, datos ya validados).
- Devuelven datos (querysets, dicts, instancias) o realizan operaciones (crear, actualizar, borrar).
- No dependen de `request`/`session` cuando no es necesario, para poder usarlos desde API sin cambios.

## Uso desde vistas web (actual)

Las vistas solo orquestan: leen parámetros del `request`, llaman al servicio y devuelven respuesta (render o redirect):

```python
# Ejemplo: clients/views.py
def get_queryset(self):
    return list_clientes_queryset(
        busqueda=self.request.GET.get('q'),
        activo=self.request.GET.get('activo'),
        order=(self.request.GET.get('order') or 'nombre').strip(),
    )
```

## Uso desde futuras API views (app móvil)

Las API views pueden usar los mismos servicios y devolver JSON:

```python
# Ejemplo futuro: clients/api_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from clients.services import list_clientes_queryset, get_cliente_detalle_data

@api_view(['GET'])
def cliente_list_api(request):
    qs = list_clientes_queryset(
        busqueda=request.query_params.get('q'),
        activo=request.query_params.get('activo'),
        order=request.query_params.get('order', 'nombre'),
    )
    # Paginación y serialización a criterio de la API
    return Response([...])

@api_view(['GET'])
def cliente_detalle_api(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    data = get_cliente_detalle_data(cliente)
    return Response(serialize_cliente_detalle(cliente, data))
```

Así se evita duplicar reglas de filtrado, ordenación o cálculo; la API y la web comparten la misma lógica.

## Validación en servicios

Donde la lógica debe fallar ante datos inválidos (p. ej. crear ingrediente con nombre vacío), los servicios lanzan `ValueError` con mensaje claro. Las vistas (web o API) capturan la excepción y devuelven el error apropiado (mensaje flash + redirect o JSON 400).
