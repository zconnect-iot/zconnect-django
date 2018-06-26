from datetime import datetime
import logging

# from rest_framework import permissions
from dateutil import parser
from django.apps import apps
from django.conf import settings
from django.core.exceptions import FieldError, ObjectDoesNotExist
from django.http import Http404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework_extensions.mixins import NestedViewSetMixin

from zconnect.messages import Message
from zconnect.permissions import IsAdminOrTimeseriesIngress
from zconnect.tasks import process_message
from zconnect.util import exceptions
from zconnect.util.date_util import InvalidDates, validate_dates
from zconnect.zc_timeseries.exceptions import DeviceLookupException
from zconnect.zc_timeseries.models import (
    DeviceSensor, SensorType, TimeSeriesData, TimeSeriesDataArchive)
from zconnect.zc_timeseries.util.tsaggregations import AGGREGATION_CHOICES

from .filters import TSArchiveFilter
from .serializers import (
    DeviceSensorSerializer, SensorTypeSerializer, TimeSeriesDataArchiveSerializer,
    TimeSeriesDataSerializer, TimeseriesHTTPIngressSerializer)

logger = logging.getLogger(__name__)

# TS data serializer is in the main package, but only enabled if
# zconenct.zc_timeseries is enabled in the packages


class SensorTypeViewSet(NestedViewSetMixin, viewsets.ModelViewSet):
    queryset = SensorType.objects.all()
    serializer_class = SensorTypeSerializer
    http_method_names = ['get']
    permission_classes = [IsAuthenticated,]


class DeviceSensorViewSet(NestedViewSetMixin, viewsets.ModelViewSet):
    queryset = DeviceSensor.objects.all()
    serializer_class = DeviceSensorSerializer
    http_method_names = ['get']
    permission_classes = [IsAuthenticated,]


class TimeSeriesDataViewSet(NestedViewSetMixin, viewsets.ModelViewSet):
    queryset = TimeSeriesData.objects.all()
    serializer_class = TimeSeriesDataSerializer
    http_method_names = ['get']
    permission_classes = [IsAuthenticated,]

    def list(self, request, parent_lookup_sensor__device):
        if "zconnect.zc_timeseries" not in settings.INSTALLED_APPS:
            logger.debug("No timeseries data app installed, returning")
            raise Http404

        try:
            start, end = validate_dates(
                self.request.query_params.get("start"),
                self.request.query_params.get("end"),
            )
        except InvalidDates as e:
            raise exceptions.BadRequestError("Invalid dates") from e

        device_pk = parent_lookup_sensor__device
        Device = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)
        device = Device.objects.get(pk=device_pk)

        resolution = self.request.query_params.get("resolution")

        logger.debug("Start = %s, end = %s, resolution = %s", start, end, resolution)

        ts_data = device.optimised_data_fetch(start, end, resolution)

        serialized = {}
        for sensor_name in ts_data:
            sd = ts_data[sensor_name]
            serializer = TimeSeriesDataSerializer(sd, many=True)
            serialized[sensor_name] = serializer.data

        return Response(serialized)


class TimeSeriesDataArchiveViewSet(NestedViewSetMixin, viewsets.ModelViewSet):
    queryset = TimeSeriesDataArchive.objects.all()
    serializer_class = TimeSeriesDataArchiveSerializer
    http_method_names = ['get']
    permission_classes = [IsAuthenticated,]

    filter_backends = [
        DjangoFilterBackend
    ]
    filter_class = TSArchiveFilter
    filter_fields = ["start", "end", "aggregation_type"]

    def list(self, request, *args, **kwargs):
        aggregation_type = self.request.query_params.get("aggregation_type")

        if aggregation_type:
            if aggregation_type not in [i[0] for i in AGGREGATION_CHOICES]:
                return Response(
                    {"detail": "'{}' is not a valid aggregation_type".format(aggregation_type)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return super().list(request, *args, **kwargs)


class TimeseriesHTTPIngressViewSet(viewsets.ViewSet):
    """ Viewset to allow inputting timeseries data over HTTP

    This allows a user to POST data to the timeseries ingress which will be
    republished over MQTT and later picked up by the watson worker.

    This is used in applications where incoming data is not sent over MQTT and
    needs to be proxied through another server.

    The get_success_headers method is copied from CreateModelMixin, didn't want
    to subclass just in case internal API changed.
    """
    _device_model = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)
    queryset = _device_model.objects.all()
    permission_classes = [IsAdminOrTimeseriesIngress,]

    def create(self, request, *args, **kwargs):
        serializer = TimeseriesHTTPIngressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        device = self.get_unknown_device(kwargs['field'], kwargs['value'])

        self.send_ts_data(serializer, device)

        headers = self.get_success_headers(serializer.data)

        response_data = serializer.data
        # Add the device ID in here, to make sure that the client can send data
        # to other endpoints too.
        response_data["device"] = device.pk

        return Response(
            response_data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )

    def get_unknown_device(self, field, field_value):
        """Because we don't know how the devices are going to identify
        themselves, some kind of unique identifier is sent in the request. Here
        we look up the device based on the given field.

        Args:
            field (str): field name on device to query on
            field_value (str): value of field to look up device

        Returns:
            Device: associated device

        Raises:
            DeviceLookupException: The given field did not exist, or a device
                with the given value for that field did not exist
        """
        filters = {
            field: field_value
        }

        try:
            device = self._device_model.objects.get(**filters)
        except (FieldError, ObjectDoesNotExist) as e:
            raise DeviceLookupException("Failed to find device with {}:{}".format(
                field, field_value
            )) from e
        return device

    def send_ts_data(self, serializer, device):
        """
        Create a ZConnect Message from the incoming data and process with
        the celery worker.
        """

        timestamp = serializer.data["timestamp"]
        if not isinstance(timestamp, datetime):
            timestamp = parser.parse(timestamp)

        message = Message(
            category="periodic",
            device=device,
            body=serializer.data["data"],
            timestamp=timestamp,
        )
        process_message.apply_async(args=[message.as_dict()])

    def get_success_headers(self, data):
        try:
            return {'Location': str(data[api_settings.URL_FIELD_NAME])}
        except (TypeError, KeyError):
            return {}
