# Routing (Route optimization API)

Optimización de orden de paradas usando **Google Maps Routes API (Routes Preferred)** con waypoint optimization, hasta **98 paradas** por coordenadas lat/lng (sin Place IDs).

## Configuración

1. **Clave API**: Definir la variable de entorno `GOOGLE_MAPS_API_KEY` (o en `.env` en la raíz del proyecto):

   ```bash
   export GOOGLE_MAPS_API_KEY="tu-clave-de-google-cloud"
   ```

   En Django se usa desde `settings.GOOGLE_MAPS_API_KEY` (ya configurado en `base/settings/base.py`).

2. Habilitar **Routes API (Directions v2)** en Google Cloud Console para el proyecto y restringir la clave por IP si aplica (servidor).

## Endpoint

- **URL**: `POST /api/routes/optimize`
- **Body (JSON)**:
  - `start`: `{ "lat": number, "lng": number }` — obligatorio.
  - `end`: `{ "lat": number, "lng": number }` — opcional; si se omite, se usa `start` (ida y vuelta).
  - `stops`: array de hasta **98** elementos `{ "id": <cualquier tipo>, "lat": number, "lng": number }`.

## Ejemplo de solicitud (cURL)

```bash
curl -X POST "http://localhost:8000/api/routes/optimize" \
  -H "Content-Type: application/json" \
  -d '{
    "start": { "lat": 40.4168, "lng": -3.7038 },
    "stops": [
      { "id": "A", "lat": 40.42, "lng": -3.70 },
      { "id": "B", "lat": 40.43, "lng": -3.71 },
      { "id": "C", "lat": 40.41, "lng": -3.69 }
    ]
  }'
```

Con destino distinto al origen:

```bash
curl -X POST "http://localhost:8000/api/routes/optimize" \
  -H "Content-Type: application/json" \
  -d '{
    "start": { "lat": 40.4168, "lng": -3.7038 },
    "end": { "lat": 40.45, "lng": -3.72 },
    "stops": [
      { "id": 1, "lat": 40.42, "lng": -3.70 },
      { "id": 2, "lat": 40.43, "lng": -3.71 }
    ]
  }'
```

## Ejemplo de respuesta (JSON)

```json
{
  "optimized_stop_ids": ["C", "A", "B"],
  "legs": [
    { "distance_meters": 2500, "duration_seconds": 420 },
    { "distance_meters": 1800, "duration_seconds": 310 },
    { "distance_meters": 3200, "duration_seconds": 510 },
    { "distance_meters": 1500, "duration_seconds": 240 }
  ],
  "polyline": "encoded_polyline_string_from_google...",
  "summary": {
    "total_distance_meters": 9000,
    "total_duration_seconds": 1480
  }
}
```

- **optimized_stop_ids**: orden recomendado de visita (ids de `stops`).
- **legs**: por cada tramo (origen → parada1 → … → destino), `distance_meters` y `duration_seconds`.
- **polyline**: polyline codificado de la ruta completa (puede ser `null` si la API no lo devuelve).
- **summary**: distancia y duración totales de la ruta.

## Errores

- **400**: validación (ej. >98 paradas, `lat`/`lng` fuera de rango, `start`/`stops` inválidos).
- **502**: error de la API de Google (cuota, 4xx/5xx); el cuerpo incluye `error` y `message`.

Ejemplo de error:

```json
{
  "error": "too_many_stops",
  "message": "stops must have at most 98 items (got 99)"
}
```
