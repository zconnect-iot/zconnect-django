import logging

from django_filters.rest_framework import FilterSet

from .models import TimeSeriesDataArchive

logger = logging.getLogger(__name__)


class TSArchiveFilter(FilterSet):
    """Allows filtering ts archive by start/end dates"""

    class Meta:
        model = TimeSeriesDataArchive
        fields = {
            "start": ["lt", "gt"],
            "end": ["lt", "gt"],
            "aggregation_type": ["exact"],
        }
