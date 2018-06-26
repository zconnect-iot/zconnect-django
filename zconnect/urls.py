from django.conf.urls import include, url
from rest_auth.views import LoginView, LogoutView, PasswordChangeView, PasswordResetConfirmView
from rest_framework_extensions.routers import ExtendedSimpleRouter

from .views import (
    ActivityStreamViewSet, ActivitySubscriptionViewSet, DeviceViewSet, EventDefinitionViewSet,
    EventViewSet, LocationViewSet, OrganizationMembershipViewSet, OrganizationViewSet,
    OrgMembershipByUserViewSet, PasswordResetView, ProductFirmwareViewSet, ProductViewSet,
    TokenRefreshSlidingView, UpdateExecutionViewSet, UserViewSet, health_check)
from .zc_timeseries.views import (
    DeviceSensorViewSet, SensorTypeViewSet, TimeSeriesDataArchiveViewSet, TimeSeriesDataViewSet,
    TimeseriesHTTPIngressViewSet)

#from rest_framework_simplejwt.views import TokenRefreshSlidingView



# from organizations.backends import invitation_backend



router = ExtendedSimpleRouter()

# Device associated endpoints
device_router = router.register(
    r'devices',
    DeviceViewSet,
    base_name="devices"
)
device_router.register(
    r'data',
    TimeSeriesDataViewSet,
    parents_query_lookups=['sensor__device'],
    base_name="data"
)
device_router.register(
    r'data_archive',
    TimeSeriesDataArchiveViewSet,
    parents_query_lookups=['sensor__device'],
    base_name="data_archive"
)
device_router.register(
    r'events',
    EventViewSet,
    parents_query_lookups=["device"],
    base_name="events",
)
device_router.register(
    r'event_defs',
    EventDefinitionViewSet,
    parents_query_lookups=["device"],
    base_name="event_defs",
)
device_router.register(
    r'sensors',
    DeviceSensorViewSet,
    parents_query_lookups=["device"],
    base_name="sensors",
)
device_router.register(
    r'activity_stream',
    ActivityStreamViewSet,
    parents_query_lookups=["actor_object_id"],
    base_name="activity_stream",
)

# Product associated endpoints
product_router = router.register(
    r'products',
    ProductViewSet,
)
product_router.register(
    r'firmware',
    ProductFirmwareViewSet,
    parents_query_lookups=["product"],
    base_name="firmware",
)
product_router.register(
    r'updates',
    UpdateExecutionViewSet,
    parents_query_lookups=["product_firmware__product"],
    base_name="updates",
)
product_router.register(
    r'sensors',
    SensorTypeViewSet,
    parents_query_lookups=["product"],
    base_name="sensors",
)

org_router = router.register(
    r'organizations',
    OrganizationViewSet,
)
org_router.register(
    r"membership",
    OrganizationMembershipViewSet,
    parents_query_lookups=["organization"],
    base_name="membership",
)
org_router.register(
    r"user",
    OrgMembershipByUserViewSet,
    parents_query_lookups=["organization"],
    base_name="user",
)

router.register(r'firmware', ProductFirmwareViewSet)
router.register(r'updates', UpdateExecutionViewSet)
router.register(r'locations', LocationViewSet)

user_router = router.register(r'users', UserViewSet)
user_router.register(
    r"subscriptions",
    ActivitySubscriptionViewSet,
    parents_query_lookups=["user"],
    base_name="subscriptions",
)

urlpatterns = [
    url(r'^', include(router.urls)),

    # url(r'^invitations/', include(invitation_backend().get_urls())),
    url(r'^auth/refresh_token/$', TokenRefreshSlidingView.as_view(), name="refresh"),

    # Timeseries ingress is a little special in that it can match any field
    # on the device.
    url(
        r'^data/(?P<field>\w+)/(?P<value>\w+)/',
        TimeseriesHTTPIngressViewSet.as_view({'post': 'create'})
    ),
    url(r'^health/$', health_check),

    # Rest Auth URLs. Copied here to avoid serving user details endpoint
    url(r'^auth/password/reset/$', PasswordResetView.as_view(),
        name='rest_password_reset'),

    url(r'^auth/password/reset/confirm/$', PasswordResetConfirmView.as_view(),
        name='rest_password_reset_confirm'),

    url(r'^auth/login/$', LoginView.as_view(), name='rest_login'),

    # URLs that require a user to be logged in with a valid session / token.
    url(r'^auth/logout/$', LogoutView.as_view(), name='rest_logout'),

    url(r'^auth/password/change/$', PasswordChangeView.as_view(),
        name='rest_password_change'),
]
