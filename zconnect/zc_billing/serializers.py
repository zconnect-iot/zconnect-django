from rest_framework import serializers

from zconnect.serializers import (
    StubBilledOrganizationSerializer, StubDeviceSerializer, StubProductSerializer)

from .models import Bill


class BillSerializer(serializers.ModelSerializer):
    organization = StubBilledOrganizationSerializer()
    devices_by_product = serializers.SerializerMethodField()

    class Meta:
        model = Bill
        fields = ("id", "created_at", "updated_at", "next_period_end",
                  "period_start", "period_end", "amount", "paid", "currency",
                  "devices_by_product", "organization")
        read_only_fields = tuple(x for x in fields if x != "paid")

    def get_devices_by_product(self, this_object):
        return [
            {
                "devices": [StubDeviceSerializer(d).data for d in x["devices"]],
                "product": StubProductSerializer(x["product"]).data,
            } for x in this_object.devices_by_product
        ]
