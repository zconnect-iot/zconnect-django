import logging

from django.core import validators
from django.db import models

from .base import ModelBase

logger = logging.getLogger(__name__)


class Location(ModelBase):
    """Location model. Allows users to be grouped with devices.

    Attributes:
        latitude (float): latitude
        longitude (float): longitude
        country (str): Country
        locality (str): country-specific 'locality' (eg, 'London')
        organization (str): Name of organization at this address
        poboxno (str): PO box number of address
        postalcode (str): Postal number of address
        region (str): country-specific 'region' (eg, 'southwest')
        street_address (str): first line of street address (eg, '123 fake street')
        address (Address): Address of this location
    """
    name = models.CharField(max_length=100, blank=True, null=True)
    timezone = models.CharField(max_length=50, blank=True, null=True)

    latitude = models.FloatField(blank=True, null=True, validators=[
        validators.MinValueValidator(-90.0),
        validators.MaxValueValidator(90.0),
    ])
    longitude = models.FloatField(blank=True, null=True, validators=[
        validators.MinValueValidator(-180.0),
        validators.MaxValueValidator(180.0),
    ])

    organization = models.CharField(max_length=50, blank=True, null=True)
    country = models.CharField(max_length=100)
    locality = models.CharField(max_length=50, blank=True, null=True)
    region = models.CharField(max_length=100)
    poboxno = models.CharField(max_length=50, blank=True, null=True)
    postalcode = models.CharField(max_length=20)
    street_address = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        ordering = ["country"]
