from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Event, EventDefinition, OrganizationLogo, Product
from .zc_timeseries.models import DeviceSensor, SensorType, TimeSeriesData

Device = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)
User = apps.get_model(settings.AUTH_USER_MODEL)


admin.site.register(SensorType)
admin.site.register(Product)
admin.site.register(Device)
admin.site.register(OrganizationLogo)

@admin.register(DeviceSensor)
class DeviceSensorAdmin(admin.ModelAdmin):
    list_filter = ('device', 'sensor_type')

@admin.register(TimeSeriesData)
class TimeSeriesDataAdmin(admin.ModelAdmin):
    list_filter = ('sensor__device', 'sensor__sensor_type__sensor_name')

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    fields = ('created_at', 'device', 'success', 'definition')
    readonly_fields = ('created_at',)
    list_filter = ('device', 'success')

@admin.register(EventDefinition)
class EventDefinitionAdmin(admin.ModelAdmin):
    list_filter = ('device', 'product', 'scheduled')

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('phone_number',)}),
    )
