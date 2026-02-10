# API de entregas y app courier (Backend-driven)

## Principio arquitectónico (muy importante)

El sistema es **impulsado por el backend**.  
Todas las reglas de negocio, transiciones de estado, validaciones, permisos y lógica de decisión viven en **Django**.  
La app móvil es un **cliente fino** que solo:

- Muestra los datos que devuelve la API
- Recoge acciones del usuario y datos del sensor (GPS)
- Envía eventos al backend

La app **nunca** decide:

- Qué parada está activa
- Si una parada puede cambiar de estado
- Cuándo notificar al cliente
- Si una entrega es válida

Esas decisiones se procesan siempre en el servidor.

---

## Stack

- **Backend:** Django + Django REST Framework, PostgreSQL, JWT (SimpleJWT), django-filter, drf-spectacular
- **App:** Flutter (solo Android), distribución por APK directo (fuera de Play Store)

---

## Backend: app `deliveries`

### Modelos

- **CourierProfile:** enlace User ↔ Entregador (rutas)
- **DeliveryRoute:** ruta del día (1:1 con `routes.Ruta`)
- **DeliveryStop:** parada con máquina de estados (PENDING → EN_ROUTE → ARRIVED → DELIVERED | FAILED)
- **CourierLocationPing:** posición GPS del courier
- **DeliveryActionEvent:** registro inmutable de acciones (idempotente por `request_id`)
- **DeliveryEventOutbox:** eventos para integraciones (notificaciones, etc.)
- **MobileAppVersion:** versión mínima y URL del APK

### Máquina de estados (parada)

Estados: `PENDING`, `EN_ROUTE`, `ARRIVED`, `DELIVERED`, `FAILED`.  
Transiciones válidas definidas en el backend; intentos inválidos responden **409 Conflict** con mensaje.

### Parada activa

El backend calcula la parada activa según:

- Orden de la ruta
- Paradas ya completadas
- (Opcional) última posición del courier

La respuesta incluye `current_active_stop_id`, `next_stop_id` y un texto de estado para la UI.

### Proximidad

El backend calcula la distancia (Haversine) entre el courier y la parada y decide si está “cerca”.  
Puede permitir o denegar transiciones a ARRIVED/DELIVERED según esa decisión.  
La app solo envía coordenadas; no calcula distancias.

### Notificaciones

El backend crea registros en **DeliveryEventOutbox** cuando:

- Una parada pasa a EN_ROUTE
- Una parada se entrega
- Una parada falla

La app no dispara notificaciones directamente.

### Idempotencia

Cada evento lleva un `request_id` (UUID).  
Reenvíos con el mismo `request_id` no modifican el estado y devuelven el contexto actual.

---

## API REST (base: `/api/v1/`)

### Autenticación JWT

- **POST** `/api/v1/auth/token/`  
  Body: `{"username": "...", "password": "..."}`  
  Respuesta: `{"access": "...", "refresh": "..."}`

- **POST** `/api/v1/auth/refresh/`  
  Body: `{"refresh": "..."}`  
  Respuesta: `{"access": "...", "refresh": "..."}`

### Courier (requiere JWT y perfil courier)

- **GET** `/api/v1/courier/context/`  
  Devuelve: perfil, ruta del día, paradas, `current_active_stop_id`, `next_stop_id`, estado legible y **allowed_actions** por parada (`can_mark_arrived`, `can_mark_delivered`, `can_mark_failed`, `reason_if_blocked`).

### Eventos

- **POST** `/api/v1/events/`  
  Body:

  ```json
  {
    "request_id": "uuid",
    "type": "LOCATION_PING" | "ATTEMPT_ARRIVE" | "ATTEMPT_DELIVER" | "ATTEMPT_FAIL",
    "stop_id": 123,
    "payload": { "latitude": 19.43, "longitude": -99.13 }
  }
  ```

  - `stop_id` obligatorio para ATTEMPT_ARRIVE, ATTEMPT_DELIVER, ATTEMPT_FAIL.  
  - Para LOCATION_PING, `payload` puede incluir `latitude` y `longitude`.  
  - Respuesta: mismo esquema que `GET /courier/context/` (contexto actualizado) o 409 con `detail` si la transición no está permitida.

### Versión app

- **GET** `/api/v1/mobile/version/?platform=ANDROID&current_version_code=123`  
  Público (sin auth).  
  Respuesta: `update_required`, `apk_url`, etc.

### Documentación OpenAPI

- **GET** `/api/schema/` — esquema OpenAPI  
- **GET** `/api/docs/` — Swagger UI

---

## Comandos

### Backend (Django)

```bash
# Entorno
cd catering
export DJANGO_SETTINGS_MODULE=base.settings.development   # o production

# Migraciones
python manage.py migrate

# Tests (app deliveries)
python manage.py test deliveries.tests

# Servidor
python manage.py runserver
```

La API estará en `http://127.0.0.1:8000/api/v1/`.  
En emulador Android, usa `http://10.0.2.2:8000/api/v1/` como base URL.

### App Flutter (courier)

Si la carpeta `courier_app` no tiene los archivos de plataforma completos, genere el proyecto Flutter desde la raíz del repo:

```bash
flutter create . --project-name courier_app
```

(dentro de `courier_app`; esto añade/actualiza `android/`, `ios/`, etc., sin borrar `lib/` ni `pubspec.yaml`.)

Luego:

```bash
cd courier_app

# Dependencias
flutter pub get

# Ejecutar en emulador/dispositivo
flutter run

# APK release
flutter build apk --release
```

El APK se genera en `build/app/outputs/flutter-apk/app-release.apk`.  
Para **permisos de ubicación** en Android, asegúrese de que `android/app/src/main/AndroidManifest.xml` incluya `ACCESS_FINE_LOCATION` y `ACCESS_COARSE_LOCATION` (ya incluidos en este proyecto).

### Deploy del APK

1. **Generar el APK** (con Flutter en el PATH):
   ```bash
   cd courier_app
   flutter pub get
   flutter build apk --release
   ```
   O desde PowerShell en `courier_app`: `.\build_apk.ps1`

2. **Ubicación del archivo:**  
   `courier_app/build/app/outputs/flutter-apk/app-release.apk`

3. **Desplegar para que los repartidores lo descarguen:**
   - **Opción A:** Subir el APK a tu servidor (por ejemplo en `https://tudominio.com/static/courier-app.apk` o en la carpeta `media/` de Django) y dar el enlace a los repartidores.
   - **Opción B:** Registrar la URL en el modelo **MobileAppVersion** (admin Django): campo `apk_url` con la URL pública del APK. La app puede consultar `GET /api/v1/mobile/version/` y, si `update_required` es true, abrir esa URL para descargar la nueva versión.
   - En Android hay que permitir “instalar desde orígenes desconocidos” para ese navegador o archivo.

4. **Configurar la URL del backend en la app:**  
   Por defecto la app usa `http://10.0.2.2:8000/api/v1` (emulador). En producción debes configurar la URL real del API (por ejemplo vía pantalla de ajustes o compilando con `--dart-define=API_BASE_URL=https://tudominio.com/api/v1` si lo añades al código).

---

## Flujo típico en la app

1. **Login:** POST a `/auth/token/`, guardar access (y refresh).
2. **Al abrir la ruta:** GET `/courier/context/` y mostrar paradas y parada activa.
3. **Cada 60–120 s (en primer plano):** POST `/events/` con `type: LOCATION_PING` y `payload: { latitude, longitude }`.
4. **Acciones del repartidor:** la app solo habilita/deshabilita botones según `can_mark_arrived`, `can_mark_delivered`, `can_mark_failed` del contexto. Al pulsar, envía el evento correspondiente (ATTEMPT_ARRIVE, ATTEMPT_DELIVER, ATTEMPT_FAIL) con `request_id` único.
5. **Offline:** la app puede encolar eventos con `request_id` y reenviarlos al recuperar conexión; el backend los trata de forma idempotente.

---

## Admin Django

En `/admin/` se gestionan:

- CourierProfile, DeliveryRoute, DeliveryStop
- CourierLocationPing, DeliveryEventOutbox, MobileAppVersion
- **DeliveryActionEvent:** solo lectura (auditoría)

En DeliveryStop el admin puede forzar cambios de estado (EN_ROUTE, ARRIVED, DELIVERED, FAILED) si hace falta.

---

## Cómo dar de alta un courier

1. Crear o usar un **Usuario** (Django auth).
2. Crear o usar un **Entregador** en la app `routes` y asignarle ese usuario.
3. Crear un **CourierProfile** (app `deliveries`) que enlace ese User con ese Entregador.
4. Asignar una **Ruta** para el día al Entregador (como hasta ahora en el sistema de rutas).  
La API de entregas usará esa ruta como “ruta del día” para ese courier.
