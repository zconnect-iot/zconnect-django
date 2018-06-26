from math import isnan

# from rest_framework import permissions
from rest_framework import serializers

from zconnect.zc_timeseries.models import (
    DeviceSensor, SensorType, TimeSeriesData, TimeSeriesDataArchive)


class TSSerializerMixin:
    def get_value(self, obj):
        if isnan(obj.value):
            return None
        else:
            return obj.value


class TimeSeriesDataSerializer(TSSerializerMixin, serializers.ModelSerializer):
    value = serializers.SerializerMethodField()

    class Meta:
        model = TimeSeriesData
        fields = ("ts", "value",)
        read_only_fields = fields


class TimeSeriesDataArchiveSerializer(TSSerializerMixin, serializers.ModelSerializer):
    value = serializers.SerializerMethodField()

    class Meta:
        model = TimeSeriesDataArchive
        fields = ("value", "start", "end", "aggregation_type")
        read_only_fields = fields


class SensorTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorType
        fields = ("id", "unit", "product", "sensor_name", "graph_type",)
        read_only_fields = ("id", "unit", "product",)


class DeviceSensorSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceSensor
        fields = ("id", "resolution", "sensor_type", "device",)
        # These should be set at object creation time
        read_only_fields = ("id", "resolution", "sensor_type",)


class TimeseriesHTTPIngressSerializer(serializers.Serializer):
    """ Serializer for incoming HTTP timeseries data.
    The incoming data should take the form of:
    {
        data: {
            "blah": "blah",
            ...
        }
        timestamp: "2013-01-29T12:34:56.000000Z"
    }

    NB. Data inside the data field is not currently fully validated.
    """
    data = serializers.DictField()
    timestamp = serializers.DateTimeField()
