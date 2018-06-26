from django.conf.urls import include, url
from rest_framework_extensions.routers import ExtendedSimpleRouter

from .views import BillViewSet

router = ExtendedSimpleRouter()
router.register(r'^bills', BillViewSet)

urlpatterns = [
    url(r'^', include(router.urls)),
]
