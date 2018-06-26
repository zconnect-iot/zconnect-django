import json
import os

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from rest_auth.utils import import_callable

from zconnect.models import Product

_Device = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)

class Command(BaseCommand):
    help = 'Provision one or more zconnect devices'

    def add_arguments(self, parser):
        parser.add_argument(
            "product",
            type=int,
            help="The product ID these devices should be assigned to"
        )

        parser.add_argument(
            "--number",
            default=1,
            type=int,
            help="The number of devices to create"
        )

        parser.add_argument(
            "--outputfile",
            default='output.json',
            type=os.path.abspath,
            help="Path to the file where output should be stored"
        )

    def handle(self, *args, **options):
        device_serializer = import_callable(settings.ZCONNECT_DEVICE_SERIALIZER)

        product_id = options['product']
        product = Product.objects.get(pk=product_id)

        devices = [_Device(product=product) for _ in range(0, options['number'])]
        for d in devices:
            d.save()
        serialized_devices = [device_serializer(d).data for d in devices]

        self.handle_output(serialized_devices, **options)

    def handle_output(self, devices, **options):
        outputfilepath = options['outputfile']

        with open(outputfilepath, 'w') as ofile:
            json.dump(devices, ofile)
