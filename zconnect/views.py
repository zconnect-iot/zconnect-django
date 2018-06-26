import abc
from distutils.util import strtobool  # pylint: disable=no-name-in-module,import-error
from itertools import filterfalse
import json
import logging

from actstream.models import Action
from cached_property import cached_property
from django.apps import apps
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import Http404
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from organizations.models import OrganizationUser
from rest_auth.utils import import_callable
from rest_auth.views import PasswordResetView as RestAuthPasswordResetView
from rest_framework import decorators, mixins, renderers, serializers, status, views, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import (
    AllowAny, DjangoObjectPermissions, IsAdminUser, IsAuthenticated)
from rest_framework.response import Response
from rest_framework_extensions.mixins import NestedViewSetMixin
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenViewBase

from zconnect.pagination import StandardPagination
from zconnect.util.profiling.sampler import Sampler

from .filters import EventDefinitionFilterSet, OrganizationObjectPermissionsFilter, UserFilterSet
from .models import (
    ActivitySubscription, Event, EventDefinition, Location, OrganizationLogo, Product,
    ProductFirmware, UpdateExecution)
from .permissions import (
    GroupPermissions, IsAdminOrReadOnly, IsAuthenticatedAdminPost, NestedGroupPermissions)
from .serializers import (
    ActionSerializer, ActivitySubscriptionSerializer, BilledOrganizationSerializer,
    CreateDeviceSerializer, CreateUserSerializer, DeviceSerializer, EventDefinitionSerializer,
    EventSerializer, LocationSerializer, OrganizationLogoSerializer,
    OrganizationMembershipSerializer, PasswordResetSerializer, ProductFirmwareSerializer,
    StubDeviceSerializer, TokenRefreshSlidingSerializer, UpdateExecutionSerializer)
from .util import exceptions
from .util.db_util import check_db
from .util.redis_util import check_redis
from .zc_billing.models import BilledOrganization
from .zc_billing.serializers import BillSerializer

logger = logging.getLogger(__name__)

Device = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)
User = apps.get_model(settings.AUTH_USER_MODEL)


class AbstractStubbableModelViewSet(viewsets.ModelViewSet, metaclass=abc.ABCMeta):

    """Abstract superclass for a viewset that will automatically parse the
    'stub' query parameter and choose a different serializer to return a stub of
    the model if it is truthy.

    This expects a stub_serializer, normal_serializer, and create_serializer to
    be set on the viewset. stub_serializer and normal_serializer are self
    explanatory. create_serializer is used when 'stub=true' is passed and we are
    trying to create a new instance of the object.

    Todo:
        Move attribute checks to __new__? This might cause some weird metaclass
        issues
    """

    def __init__(self, *args, **kwargs):
        try:
            assert issubclass(self.stub_serializer, serializers.ModelSerializer)
            assert issubclass(self.normal_serializer, serializers.ModelSerializer)
            assert issubclass(self.create_serializer, serializers.ModelSerializer)
        except AttributeError as e:
            if "create_serializer" in e.args[0]:
                logger.info("There is no `create_serializer` attribute on %s, will use `normal_serializer` on POST requests", type(self))
            else:
                raise AttributeError("Stubbable viewsets must have a stub_serializer and normal_serializer attribute") from e
        except AssertionError as e:
            raise AttributeError("stub/normal/create serializer on stubbable viewset must be a subclass of ModelSerializer") from e

        super().__init__(*args, **kwargs)

    def get_serializer_class(self):
        """Check which serializer to get based on the 'stub' query parameter.

        Look at the documentation for strtobool to see which values are
        considered 'truthy' for this parameter.
        """
        is_stub = self.request.query_params.get("stub", None)
        if is_stub is not None:
            is_stub = strtobool(is_stub)

        if is_stub:
            return self.stub_serializer
        else:
            if self.request.method == "POST" and getattr(self, "create_serializer", None) is not None:
                return self.create_serializer
            return self.normal_serializer


class NestedViewSetMixinWithPermissions(NestedViewSetMixin):

    """Override NestedViewSetMixin method to also filter based on parent
    permissions

    This provides an extension of drf-extensions' nested viewset mixin that will
    first check to see if the user has permission to access a 'parent' object -
    for example, when accessing a device's data, make sure the user has
    permission to access the device as well.

    Requires parent_viewset_class to be set on the viewset, which is used to
    check permissions of the parent object.
    """

    def __init__(self, *args, **kwargs):
        # Is this ever called?
        try:
            assert issubclass(self.parent_viewset_class, viewsets.ModelViewSet)
        except AttributeError as e:
            raise AttributeError("Nested viewsets must define a parent_viewset_class") from e
        except AssertionError as e:
            raise AttributeError("parent_viewset_class must be a ModelViewSet class") from e

        super().__init__(*args, **kwargs)

    @cached_property
    def get_parent_viewset(self):
        cls = self.parent_viewset_class
        cls.lookup_field = getattr(cls, 'lookup_field', 'pk')
        cls.lookup_url_kwarg = getattr(cls, 'lookup_url_kwarg', None) or cls.lookup_field

        def is_objperm_class(perm_cls):
            return issubclass(perm_cls, DjangoObjectPermissions)

        dop_classes = list(filter(is_objperm_class, cls.permission_classes))

        if dop_classes:
            non_dop_classes = list(filterfalse(is_objperm_class, cls.permission_classes))
            new_perm_classes = non_dop_classes + [NestedGroupPermissions]
            cls.permission_classes = new_perm_classes

        return cls

    def get_parent_object(self):
        return list(self.get_parents_query_dict().values())[0]

    def get_parents_query_dict(self):
        """Initialise the parent viewset with the kwargs that are relevant only
        to querying that queryset, using the same request (for permissions),
        then look up the object. This will raise a 404/403 whatever if it fails.
        """
        from rest_framework_extensions.settings import extensions_api_settings
        vs = self.get_parent_viewset()
        vs_kwargs = {}

        query_lookup = None

        for kwarg_name, kwarg_value in self.kwargs.items():
            if kwarg_name.startswith(extensions_api_settings.DEFAULT_PARENT_LOOKUP_KWARG_NAME_PREFIX):
                # Specific to querying the parent. something like
                # `parent_lookup_device` -> device
                query_lookup = kwarg_name.replace(
                    extensions_api_settings.DEFAULT_PARENT_LOOKUP_KWARG_NAME_PREFIX,
                    '',
                    1
                )
                # something like `pk`
                vs_kwargs[vs.lookup_field] = kwarg_value
                break

        vs.kwargs = vs_kwargs
        vs.request = self.request
        obj = vs.get_object()

        result = {query_lookup: obj}

        return result


class ProductFirmwareViewSet(NestedViewSetMixin, viewsets.ModelViewSet):
    queryset = ProductFirmware.objects.all()
    serializer_class = ProductFirmwareSerializer
    permission_classes = [IsAdminUser,]


class UpdateExecutionViewSet(NestedViewSetMixin, viewsets.ModelViewSet):
    queryset = UpdateExecution.objects.all()
    serializer_class = UpdateExecutionSerializer
    permission_classes = [IsAdminUser,]


class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = BilledOrganization.objects.all()
    serializer_class = BilledOrganizationSerializer
    permission_classes = [IsAdminUser,]

    @decorators.detail_route(methods=["get"])
    def bills(self, request, pk):
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied
        if "zconnect.zc_billing" not in settings.INSTALLED_APPS:
            raise Http404

        org = self.get_object()
        bills = org.bills_covering_period()
        serializer = BillSerializer(self.paginate_queryset(bills), many=True,
                                    context={'request': request})
        return self.get_paginated_response(serializer.data)

    @decorators.detail_route(methods=["get", "post", "delete"])
    def logo(self, request, pk):
        if request.method == "GET":
            logo = get_object_or_404(OrganizationLogo, organization=pk)
            return Response(OrganizationLogoSerializer(logo).data)

        if request.method == "POST":
            OrganizationLogo.objects.filter(organization=pk).delete()
            data = {
                "organization": pk,
                "image": request.FILES['image']
            }

            serializer = OrganizationLogoSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            return Response(serializer.data)

        if request.method == "DELETE":
            OrganizationLogo.objects.filter(organization=pk).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)


class OrganizationMembershipViewSet(NestedViewSetMixinWithPermissions,
                                    mixins.CreateModelMixin,
                                    mixins.RetrieveModelMixin,
                                    # mixins.UpdateModelMixin,
                                    mixins.DestroyModelMixin,
                                    mixins.ListModelMixin,
                                    viewsets.GenericViewSet):
    """Can create/get/delete but not modify an existing membership. That seems
    like it might get confusing and has no real semantic use (eg, changing a
    membership to refer to a different user is a bit pointless when you could
    just create a new one)

    Need to manually override perform_create() because it needs to be done in a
    special way
    """
    queryset = OrganizationUser.objects.all().order_by("user")
    serializer_class = OrganizationMembershipSerializer
    permission_classes = [IsAuthenticated,]

    parent_viewset_class = OrganizationViewSet

    filter_backends = [
        DjangoFilterBackend
    ]

    def create(self, request, *args, **kwargs):
        """ Add the organization from the path params (so we don't need to
            pass it in the request body) and check for duplicates
        """
        request.data.update({"organization": self.get_parent_object().id})

        # The unique_together validator doesn't play nicely with the stubs and
        # writable nested serializers for some reason, so roll our own version
        duplicates = self.queryset.filter(user=request.data["user"]["id"],
                                  organization=request.data["organization"])
        if duplicates:
            msg = "That user is already a member of that Organization"
            raise exceptions.BadRequestError(msg)

        return super().create(request, *args, **kwargs)


class OrgMembershipByUserViewSet(NestedViewSetMixinWithPermissions,
                                 mixins.RetrieveModelMixin,
                                 mixins.DestroyModelMixin,
                                 mixins.ListModelMixin,
                                 viewsets.GenericViewSet):
    queryset = OrganizationUser.objects.all().order_by("user")
    serializer_class = OrganizationMembershipSerializer
    permission_classes = [IsAuthenticated,]

    parent_viewset_class = OrganizationViewSet

    filter_backends = [
        DjangoFilterBackend
    ]

    http_method_names = ["get", "delete"]

    # So a url of `/api/v3/organizations/{org_id}/user/{user_id}` can be used
    lookup_field = "user"


class EventViewSet(NestedViewSetMixin, viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated,]


class ProductViewSet(NestedViewSetMixin, viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = import_callable(settings.ZCONNECT_PRODUCT_SERIALIZER)
    permission_classes = [IsAdminOrReadOnly,]


class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticated,]


class DeviceViewSet(NestedViewSetMixin, AbstractStubbableModelViewSet):
    queryset = Device.objects.all()
    pagination_class = StandardPagination

    permission_classes = [
        GroupPermissions, # subclass of DjangoObjectPermissions, to go in tandem with filter below
        IsAuthenticated,
    ]

    stub_serializer = StubDeviceSerializer
    normal_serializer = DeviceSerializer
    create_serializer = CreateDeviceSerializer

    filter_backends = [
        DjangoFilterBackend,
        OrganizationObjectPermissionsFilter,
    ]
    filter_fields = ["name"]


class EventDefinitionViewSet(NestedViewSetMixinWithPermissions, viewsets.ModelViewSet):
    queryset = (
        EventDefinition.objects
        .all()
        .filter(deleted=False)
        .order_by("ref")
    )
    serializer_class = EventDefinitionSerializer
    permission_classes = [IsAuthenticated,]

    parent_viewset_class = DeviceViewSet

    filter_backends = [
        DjangoFilterBackend
    ]
    filter_class = EventDefinitionFilterSet

    def create(self, request, *args, **kwargs):
        # As device id is provided in the path params rather than the payload
        # need to add it here, note that it is write_only field in
        # `ActivitySubscriptionSerializer`
        request.data.update({"device": self.get_parent_object().id})
        return super().create(request, *args, **kwargs)

    def perform_destroy(self, instance):
        event_def = self.get_object()
        event_def.deleted = True
        event_def.save()

class ActivityStreamViewSet(NestedViewSetMixinWithPermissions, viewsets.ModelViewSet):
    serializer_class = ActionSerializer
    permission_classes = [IsAuthenticated,]
    http_method_names = ["get"]

    parent_viewset_class = DeviceViewSet

    filter_backends = [
        DjangoFilterBackend
    ]

    def get_queryset(self):
        # The Action model from `django-activity-stream` does not store FK's
        # to related database objects, it references the actor, target, etc.
        # using only their `id` e.g. actor_object_id, target_object_id,
        # action_object_object_id
        # The following code will build a query object like
        # `{'actor_object_id': 1}` if `parents_query_lookups=["actor_object_id"]`
        # in the `ExtendedSimpleRouter` in the `urls` file
        query = {x: y.id for x, y in self.get_parents_query_dict().items()}
        return Action.objects.filter(**query)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.exclude(username='AnonymousUser').order_by("username")
    permission_classes = [IsAuthenticatedAdminPost,]

    filter_backends = [
        DjangoFilterBackend
    ]
    filter_class = UserFilterSet

    def get_serializer_class(self):
        if self.request.user.is_staff or self.request.user.is_superuser:
            if self.request.method == 'POST':
                return CreateUserSerializer
            return import_callable(settings.ZCONNECT_ADMIN_USER_SERIALIZER)
        return import_callable(settings.ZCONNECT_USER_SERIALIZER)

    @classmethod
    def update_user_password(cls, request, **kwargs):
        """ Function which updates user password if password provided in request body """
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)
        if "password" in body:
            user = User.objects.get(pk=kwargs["pk"])
            try:
                validate_password(body["password"], user=user)
            except ValidationError as exception:
                raise DRFValidationError({"password": exception.messages})
            else:
                user.set_password(body["password"])
                user.save()

    def update(self, request, *args, **kwargs):
        self.update_user_password(request, **kwargs)
        return super(UserViewSet, self).update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        self.update_user_password(request, **kwargs)
        return super(UserViewSet, self).partial_update(request, *args, **kwargs)


class ActivitySubscriptionViewSet(NestedViewSetMixinWithPermissions, viewsets.ModelViewSet):
    queryset = ActivitySubscription.objects.all().order_by("id")
    serializer_class = ActivitySubscriptionSerializer
    permission_classes = [IsAuthenticated,]
    pagination_class = None

    parent_viewset_class = UserViewSet

    filter_backends = [
        DjangoFilterBackend
    ]

    def create(self, request, *args, **kwargs):
        # As user id is provided in the path params rather than the payload
        # need to add it here, note that it is write_only field in
        # `ActivitySubscriptionSerializer`
        request.data.update({"user": self.get_parent_object().id})
        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError as exception:
            if str(exception) == 'UNIQUE constraint failed':
                raise DRFValidationError({
                    "code": "duplicate_activity_subscription",
                    "detail": "Cannot add duplicate subscription"
                    })
            else:
                raise exception

    def update(self, request, *args, **kwargs):
        request.data.update({"user": self.get_parent_object().id})
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        request.data.update({"user": self.get_parent_object().id})
        return super().partial_update(request, *args, **kwargs)


class TokenRefreshSlidingView(TokenViewBase):
    """
    Takes a refresh type JSON web token and returns an access type JSON web
    token if the refresh token is valid.
    """
    serializer_class = TokenRefreshSlidingSerializer


class StackSamplerView(views.APIView):

    """Basic viewset to get stack sampler data (if enabled)
    """

    permission_classes = []
    renderer_classes = [renderers.StaticHTMLRenderer]

    @classmethod
    def as_view(cls, **kwargs):
        """Enable the sample and create the viewset

        This needs to be done here because it should only be called once, at the
        beginning of the program.
        """
        if settings.ENABLE_STACKSAMPLER:
            cls.sampler = Sampler()
            cls.sampler.start()

        return super().as_view(**kwargs)

    def get(self, request, *args, **kwargs):
        if not settings.ENABLE_STACKSAMPLER:
            return Response("", status=status.HTTP_200_OK)

        if "localhost" not in request.META["HTTP_HOST"]:
            return Response(status=status.HTTP_404_NOT_FOUND)

        reset = request.query_params.get("reset")

        result = self.sampler.output_stats()

        if reset:
            self.sampler.reset()

        return Response(result, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes((AllowAny,))
def health_check(request):
    body = {
        "database_ok": check_db(),
        "redis_ok": check_redis()
    }
    code = 200 if body["database_ok"] and body["redis_ok"] else 500
    return Response(body, status=code)


class CeleryMQTTTestViewSet(viewsets.ViewSet):
    """Posts a task to celery which then sends an mqtt message

    This is not necessarily meant for use on a live server (though it should
    work), but can be used in integration tests to make sure the whole chain of
    processes works
    """

    # ONLY allow an admin with a jwt to access this
    permission_classes = [IsAdminUser]
    authentication_classes = [JWTAuthentication]

    def create(self, request, *args, **kwargs):
        logger.debug("Sending celery/mqtt test")
        from .serializers import MQTTMessageSerializer
        serializer = MQTTMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        from .tasks import send_mqtt_message
        send_mqtt_message.apply_async(args=(data["topic"], data["payload"]))

        return Response(
            status=status.HTTP_201_CREATED,
        )


class PasswordResetView(RestAuthPasswordResetView):
    """
    Overrides the rest_auth PasswordResetView so that we can override the
    serializer.
    """
    serializer_class = PasswordResetSerializer
