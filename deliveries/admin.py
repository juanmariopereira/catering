"""
Admin for deliveries app: full visibility and manual override.
DeliveryActionEvent is read-only for audit.
"""
from django.contrib import admin
from .models import (
    CourierProfile,
    DeliveryRoute,
    DeliveryStop,
    CourierLocationPing,
    DeliveryActionEvent,
    DeliveryEventOutbox,
    MobileAppVersion,
    StopState,
)


@admin.register(CourierProfile)
class CourierProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'entregador', 'created_at']
    search_fields = ['user__username', 'entregador__nombre']
    raw_id_fields = ['user', 'entregador']


@admin.register(DeliveryRoute)
class DeliveryRouteAdmin(admin.ModelAdmin):
    list_display = ['id', 'ruta', 'date_display', 'created_at']
    list_filter = ['ruta__fecha']
    raw_id_fields = ['ruta']
    readonly_fields = ['created_at', 'updated_at']

    def date_display(self, obj):
        return obj.date
    date_display.short_description = 'Date'


@admin.register(DeliveryStop)
class DeliveryStopAdmin(admin.ModelAdmin):
    list_display = ['id', 'delivery_route', 'sequence', 'state', 'ruta_cliente', 'updated_at']
    list_filter = ['state', 'delivery_route']
    raw_id_fields = ['delivery_route', 'ruta_cliente']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['mark_en_route', 'mark_arrived', 'mark_delivered', 'mark_failed']

    def mark_en_route(self, request, queryset):
        for stop in queryset.filter(state=StopState.PENDING):
            stop.state = StopState.EN_ROUTE
            stop.save(update_fields=['state', 'updated_at'])
        self.message_user(request, f'Updated {queryset.count()} stop(s) to EN_ROUTE.')
    mark_en_route.short_description = 'Mark selected as EN_ROUTE'

    def mark_arrived(self, request, queryset):
        for stop in queryset.filter(state=StopState.EN_ROUTE):
            stop.state = StopState.ARRIVED
            stop.save(update_fields=['state', 'updated_at'])
        self.message_user(request, f'Updated {queryset.count()} stop(s) to ARRIVED.')
    mark_arrived.short_description = 'Mark selected as ARRIVED'

    def mark_delivered(self, request, queryset):
        for stop in queryset.filter(state=StopState.ARRIVED):
            stop.state = StopState.DELIVERED
            stop.save(update_fields=['state', 'updated_at'])
            from .services.event_processor import _sync_ruta_cliente_delivered
            _sync_ruta_cliente_delivered(stop)
        self.message_user(request, f'Updated {queryset.count()} stop(s) to DELIVERED.')
    mark_delivered.short_description = 'Mark selected as DELIVERED'

    def mark_failed(self, request, queryset):
        for stop in queryset.filter(state__in=[StopState.EN_ROUTE, StopState.ARRIVED]):
            stop.state = StopState.FAILED
            stop.save(update_fields=['state', 'updated_at'])
            from .services.event_processor import _sync_ruta_cliente_failed
            _sync_ruta_cliente_failed(stop, reason='Admin override')
        self.message_user(request, f'Updated {queryset.count()} stop(s) to FAILED.')
    mark_failed.short_description = 'Mark selected as FAILED'


@admin.register(CourierLocationPing)
class CourierLocationPingAdmin(admin.ModelAdmin):
    list_display = ['id', 'courier', 'delivery_route', 'latitude', 'longitude', 'created_at']
    list_filter = ['delivery_route']
    raw_id_fields = ['courier', 'delivery_route']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(DeliveryActionEvent)
class DeliveryActionEventAdmin(admin.ModelAdmin):
    """Read-only view of courier action events for audit."""
    list_display = ['id', 'request_id', 'courier', 'stop', 'action_type', 'created_at']
    list_filter = ['action_type', 'created_at']
    raw_id_fields = ['courier', 'stop']
    readonly_fields = ['request_id', 'courier', 'stop', 'action_type', 'payload', 'created_at']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DeliveryEventOutbox)
class DeliveryEventOutboxAdmin(admin.ModelAdmin):
    list_display = ['id', 'event_type', 'stop', 'sent_at', 'created_at']
    list_filter = ['event_type']
    raw_id_fields = ['stop']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(MobileAppVersion)
class MobileAppVersionAdmin(admin.ModelAdmin):
    list_display = ['platform', 'version_code', 'min_version_code', 'apk_url', 'updated_at']
    list_filter = ['platform']
    readonly_fields = ['created_at', 'updated_at']
