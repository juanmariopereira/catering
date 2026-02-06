from django.apps import AppConfig


class DeliveryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'delivery'
    verbose_name = 'Entregas'

    def ready(self):
        import delivery.signals  # noqa: F401 - conecta señales (contrato coords → recalcular rutas)
