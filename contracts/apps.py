from django.apps import AppConfig


class ContractsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'contracts'

    def ready(self):
        from django.db.models.signals import post_save, post_delete, pre_save
        from django.dispatch import receiver
        from base.models import Feriado
        from contracts.models import recalcular_fecha_fin_por_feriado

        # Guardar fecha anterior en actualización de Feriado para recalcular
        _feriado_old_fecha = {}

        @receiver(pre_save, sender=Feriado)
        def feriado_pre_save(sender, instance, **kwargs):
            if instance.pk:
                try:
                    old = Feriado.objects.get(pk=instance.pk)
                    _feriado_old_fecha[instance.pk] = old.fecha
                except Feriado.DoesNotExist:
                    pass

        @receiver(post_save, sender=Feriado)
        def feriado_post_save(sender, instance, created, **kwargs):
            if created:
                recalcular_fecha_fin_por_feriado(instance.fecha, +1)
            else:
                old_f = _feriado_old_fecha.pop(instance.pk, None)
                if old_f is not None and old_f != instance.fecha:
                    recalcular_fecha_fin_por_feriado(old_f, -1)
                    recalcular_fecha_fin_por_feriado(instance.fecha, +1)

        @receiver(post_delete, sender=Feriado)
        def feriado_post_delete(sender, instance, **kwargs):
            _feriado_old_fecha.pop(instance.pk, None)
            recalcular_fecha_fin_por_feriado(instance.fecha, -1)
