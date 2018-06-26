from collections import OrderedDict
import logging

# The following are all required only for overriding the refreshtokenserializer
from actstream.models import Action
from django.apps import apps
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.six import text_type
from drf_writable_nested import WritableNestedModelSerializer
from organizations.models import Organization, OrganizationUser
from rest_auth.serializers import PasswordResetSerializer as RestAuthPasswordResetSerializer
from rest_auth.utils import import_callable
from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework_simplejwt.serializers import TokenObtainSlidingSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import SlidingToken

from zconnect.util.date_util import get_now_timestamp
from zconnect.util.timezones import get_timezone_no_matter_what

from .models import (
    ActivitySubscription, Event, EventDefinition, Location, OrganizationLogo, Product,
    ProductFirmware, UpdateExecution)
from .zc_billing.models import BilledOrganization
from .zc_timeseries.serializers import TimeSeriesDataSerializer

# from organizations.models import Organization


logger = logging.getLogger(__name__)

##########################################
# NOTE
# Ideally we would use HyperlinkedModelSerializer, but it causes all kinds of
# issues with foreign keys where it will raise exceptions that have absolutely
# no bearing on the actual problem. Just use modelserializer
# NOTE
##########################################

class StubSerializerMixin():
    """StubSerializerMixin for use in any Serializers where a stubbed
    response is required. To make the requests symmetrical across request
    types, it intakes stubbed data, does not create or update in
    the usual manor, and rather returns the instance matching the id
    """
    def to_internal_value(self, data):
        if "id" in data:
            return OrderedDict({"id": data["id"]})
        return OrderedDict()

    def create(self, validated_data):
        """ Doesn't "create" anything, just loads a model """
        model = self.Meta.model
        try:
            instance = model.objects.get(id=validated_data["id"])
        except model.DoesNotExist:
            raise DRFValidationError({
                "code": "stub_serializer",
                "detail": "There is no {} with id {}"
                .format(model.__name__, validated_data["id"])
                })
        return instance

    def update(self, instance, validated_data):
        return self.create(validated_data)


class StubUserSerializer(StubSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = apps.get_model(settings.AUTH_USER_MODEL)
        fields = ("id", "email",)
        read_only_fields = fields


class StubOrganizationSerializer(StubSerializerMixin, serializers.ModelSerializer):
    """ Basic generic stub serializer for organizations """
    class Meta:
        model = Organization
        fields = ("name", "id",)
        read_only_fields = ("name", "id",)

# Serializers define the API representation.
class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "version", "name", "iot_name", "sku", "manufacturer",
            "url", "support_url", "previous_version", "periodic_data",
            "periodic_data_interval_short", "periodic_data_num_intervals_short",
            "periodic_data_interval_long", "periodic_data_num_intervals_long",
            "periodic_data_retention_short", "server_side_events",
            "battery_voltage_full", "battery_voltage_critical",
            "battery_voltage_low", "created_at", "updated_at",)
        # Don't want to be able to change the version on the fly
        read_only_fields = ("id", "created_at", "updated_at",)


class StubProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name",)
        read_only_fields = fields


class ProductFirmwareSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductFirmware
        fields = ("id", "product", "download_url", "major", "minor", "patch",
                  "prerelease", "build", "created_at", "updated_at",)
        # Don't want to be able to change the version on the fly
        read_only_fields = ("id", "product", "created_at", "updated_at",)


class StubDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)
        # RTR specific fields `site`, `online` and `sim_number` have been added
        # here for now. When there are more than one implementations of
        # `Device` will need multiple serializers
        fields = ("id", "name",)
        read_only_fields = fields


class DeviceSerializer(serializers.ModelSerializer):
    sensors_current = serializers.SerializerMethodField()
    product = StubProductSerializer()

    class Meta:
        model = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)
        fields = ("id", "product", "name", "online", "last_seen", "fw_version",
                  "sensors_current", "orgs", "online",
                  "created_at", "updated_at",)
        read_only_fields = ("id", "product", "orgs", "created_at",
                            "updated_at",)

    def get_sensors_current(self, device):
        ts_data = device.get_latest_ts_data()
        for sensor in ts_data:
            ts_data[sensor] = TimeSeriesDataSerializer(ts_data[sensor]).data
        return ts_data


class CreateDeviceSerializer(serializers.ModelSerializer):
    """ Serializer for creating device, need to be able to write to product """
    class Meta:
        model = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)
        fields = ("id", "product", "name", "online", "last_seen", "fw_version",
                  "orgs", "online", "created_at",
                  "updated_at",)
        read_only_fields = ("id", "created_at", "updated_at",)


class UpdateExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UpdateExecution
        fields = ("id", "product_firmware", "enabled", "strategy_class",
                  "created_at", "updated_at",)
        read_only_fields = ("id", "product_firmware", "created_at",
                            "updated_at",)


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ("id", "device", "definition", "success", "created_at",
                  "updated_at",)
        read_only_fields = ("id", "device", "definition", "created_at",
                            "updated_at",)


class EventDefinitionSerializer(serializers.ModelSerializer):
    actions = serializers.JSONField()

    class Meta:
        model = EventDefinition
        fields = ("id", "enabled", "ref", "condition", "actions",
                  "debounce_window", "scheduled", "single_trigger", "product",
                  "device", "created_at", "updated_at",)
        read_only_fields = ("id", "created_at", "updated_at",)
        extra_kwargs = {
            "device": {"write_only": True}
        }


class ActionSerializer(serializers.ModelSerializer):
    severity = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    notify = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = Action
        fields = ("verb", "description", "severity", "category", "notify",
                  "created_at",)
        read_only_fields = ("verb", "description", "severity", "category",
                            "notify", "created_at",)

    def get_severity(self, action):
        return action.data["severity"]

    def get_category(self, action):
        return action.data["category"]

    def get_notify(self, action):
        return action.data["notify"]

    def get_created_at(self, action):
        return action.timestamp


class ActivitySubscriptionSerializer(WritableNestedModelSerializer):
    organization = StubOrganizationSerializer()

    class Meta:
        model = ActivitySubscription
        fields = ("id", "organization", "category", "min_severity", "type", "user")
        read_only_fields = ("id",)
        extra_kwargs = {
           'user': {"write_only": True}
        }

class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ("id", "name", "timezone", "latitude", "longitude",
                  "organization", "country", "locality", "region", "poboxno",
                  "postalcode", "street_address", "created_at", "updated_at",)
        # Timezone is calculated automatically
        read_only_fields = ("id", "timezone", "created_at", "updated_at",)

    def validate(self, attrs):
        """Update timezone on save/update

        If somebody posts with {"latitude": null, "timezone": ""} then this WILL
        NOT be called and the location will have an invalid timezone!
        """

        # A latitude or longitude could be 0
        if attrs.get("latitude") is not None and attrs.get("longitude") is not None:
            attrs["timezone"] = get_timezone_no_matter_what(
                attrs["latitude"],
                attrs["longitude"]
            )

            # In the vanishingly rare case that this returns None, this should
            # probably raise an error. To make this easier for the app at the
            # moment we are setting the timezone to UTC. This would only ever
            # happen if the user tried to set up their climair more than 7
            # degrees from land.
            if attrs["timezone"] is None:
                logger.warning("Timezone on location %s set to Etc/UTC since no timezone found", attrs.get("id", None))
                attrs["timezone"] = 'Etc/UTC'

        return attrs


class OrganizationLogoSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationLogo
        fields = ("id", "organization", "image")


class BilledOrganizationSerializer(serializers.ModelSerializer):
    logo = serializers.SerializerMethodField()

    class Meta:
        model = BilledOrganization
        fields = ("id", "name", "slug", "is_active", "users", "logo")
        read_only_fields = fields

    def get_logo(self, instance):
        try:
            logo = OrganizationLogo.objects.get(organization=instance.id)
        except OrganizationLogo.DoesNotExist:
            return None
        else:
            serialized = OrganizationLogoSerializer(logo)
            return serialized.data["image"]


class StubBilledOrganizationSerializer(serializers.ModelSerializer):

    class Meta:
        model = BilledOrganization
        fields = ("id", "name",)
        read_only_fields = fields


class BaseUserSerializer(serializers.ModelSerializer):
    """To be used as the base serializer for all user serializers

    This provides the utility to be able to dump organizations from a user based
    on the org_types dictionary defined on the serializer

    Make sure that 'orgs' is in the 'fields'
    """

    org_type_map = {}

    orgs = serializers.SerializerMethodField(read_only=True)

    def get_orgs(self, obj):
        """Get dictionary of all orgs

        Note that the logging statements are in particularly chosen positions to
        avoid it hitting the database a lot

        See
        https://www.mail-archive.com/django-users@googlegroups.com/msg67486.html
        """
        raw_user_orgs = obj.orgs.all()

        # Converting to a list to log saves it requerying the DB
        orgs_as_list = [o for o in raw_user_orgs]
        logger.debug("%d orgs on object (%s): %s", len(raw_user_orgs), obj, orgs_as_list)

        def get_orgs_by_type(org_type, serializer):
            member_of = org_type.objects.filter(pk__in=[i.id for i in raw_user_orgs])
            serialized = serializer(member_of, many=True).data
            logger.debug("Orgs for %s: %s", org_type, serialized)
            return serialized

        logger.debug("Dumping organizations: %s", self.org_type_map)

        serialized_user_orgs = []
        for name, (model, serializer) in self.org_type_map.items():
            for serialized in get_orgs_by_type(model, serializer):
                serialized_user_orgs.append({
                    "type": name,
                    **serialized
                })

        # Get any extra organizations
        # This is done separately after the fact to avoid duplicates appearing
        extra = [i for i in raw_user_orgs if i.id not in [j["id"] for j in serialized_user_orgs]]
        serialized_extra = StubBilledOrganizationSerializer(extra, many=True).data
        logger.debug("Normal organizations: %s", serialized_extra)
        for s in serialized_extra:
            s.update({
                "type": "organization",
            })

        serialized_user_orgs.extend(serialized_extra)

        logger.debug("Orgs: %s", serialized_user_orgs)

        return serialized_user_orgs

    def create(self, validated_data):
        UserModel = apps.get_model(settings.AUTH_USER_MODEL)
        user_obj = UserModel(**validated_data)
        user_obj.set_password(validated_data['password'])
        user_obj.save()
        return user_obj

    def validate(self, attrs):
        """ Check the password is OK and then run standard validation """
        groupless_data = attrs.copy()
        groupless_data.pop("groups", None)
        groupless_data.pop("orgs", None)
        user = apps.get_model(settings.AUTH_USER_MODEL)(**groupless_data)
        password = attrs.get("password")

        if password:
            try:
                # Need to pass in user to check attribute similarity
                validate_password(password, user=user)
            except ValidationError as exception:
                raise DRFValidationError({"password": exception.messages})

        return super().validate(attrs)


class UserSerializerAdmin(BaseUserSerializer):
    class Meta:
        model = apps.get_model(settings.AUTH_USER_MODEL)
        fields = ("id", "email", "is_active", "date_joined", "is_staff",
                  "username", "last_login", "is_superuser", "last_name",
                  "first_name", "groups", "orgs", "created_at", "updated_at",
                  "phone_number")
        read_only_fields = ("id", "orgs", "created_at", "updated_at",)


class CreateUserSerializer(BaseUserSerializer):
    class Meta:
        model = apps.get_model(settings.AUTH_USER_MODEL)
        fields = ("id", "email", "is_active", "date_joined", "is_staff",
                  "username", "last_login", "is_superuser", "last_name",
                  "first_name", "orgs", "groups", "created_at", "updated_at",
                  "password", "phone_number")
        read_only_fields = ("id", "date_joined", "is_staff", "is_active",
                            "last_login", "is_superuser", "groups", "orgs",
                            "created_at", "updated_at",)
        extra_kwargs = {'password': {'write_only': True}}


class UserSerializer(BaseUserSerializer):
    class Meta:
        model = apps.get_model(settings.AUTH_USER_MODEL)
        fields = ("id", "email", "is_active", "date_joined", "is_staff",
                  "username", "last_login", "is_superuser", "last_name",
                  "first_name", "groups", "orgs", "created_at", "updated_at",
                  "phone_number")
        read_only_fields = ("id", "email", "date_joined", "is_staff",
                            "is_active", "last_login", "is_superuser",
                            "groups", "orgs", "created_at", "updated_at")



class JWTUserSerializer(BaseUserSerializer):
    """Serialize a user object to go into a JWT

    This should define 'fields' as any fields that should go into the JWT.
    simplejwt puts user_id in by default - this should specify any EXTRA fields
    to go in.
    """

    is_superuser = serializers.BooleanField()
    is_staff = serializers.BooleanField()
    iat = serializers.IntegerField(read_only=True, default=get_now_timestamp)

    # NOTE
    # Not currently using these ones:
    # These need to be commented out or drf complains

    # # Could replace user_id with this
    # sub = serializers.ModelField(model_field="email")
    # # Not sure what this actually is
    # iss = serializers.CharField(read_only=True, default="Zoetrope")
    # # Needs modifying/forking simplejwt for this one to work
    # aud = serializers.CharField(read_only=True, default=settings.ALLOWED_HOSTS)

    class Meta:
        model = apps.get_model(settings.AUTH_USER_MODEL)
        fields = ("email", "orgs", "is_superuser", "is_staff", "iat")
        read_only_fields = fields


class TokenWithUserObtainSerializer(TokenObtainSlidingSerializer):
    """This is used to verify the input - rest auth requires the 'user' field,
    so this serializer just adds it to the validated data"""

    def validate(self, attrs):
        data = super().validate(attrs)

        # extra
        data["user"] = self.user

        return data


def jwt_create_token(token_model, user, serializer):
    """Create the token to return

    Token from simplejwt overrides __str__ which calls jwt.encode. - This
    function returns the instance, then the serializer calls __str__ when it's
    serializing it. This function creates the instance, then injects some extra
    fields for when it gets serialized

    Args:
        token_model: REST_AUTH_TOKEN_MODEL
        user: logged in user
        serializer: REST_AUTH_SERIALIZERS::TOKEN_SERIALIZER

    Returns:
        dict: Token instance.
    """
    # FIXME
    # Fork simplejwt or create a new TokenBackend class - might just have to
    # monkeypatch it in simplejwt/state.py
    token = token_model.for_user(user)

    serializer = import_callable(settings.ZCONNECT_JWT_SERIALIZER)

    extra_user_data = serializer(user).data
    # no update() method
    for k, v in extra_user_data.items():
        token[k] = v

    logger.debug("Claims: %s", token.payload)
    return token


class TokenReturnSerializer(serializers.Serializer):
    """Serializes the RESPONSE

    See Token model in simplejwt for which ones are actually available"""
    token = serializers.CharField(allow_blank=False, allow_null=False,
                                  source="__str__")
    token_type = serializers.CharField()


class TokenRefreshSlidingSerializer(serializers.Serializer):

    """Similar to the default TokenRefreshSlidingSerializer from
    rest_framework_simplejwt, but doesn't verify the token when it loads it.

    There are 2 claims in the token, 'exp' and 'refresh_exp'. 'refresh_exp' is
    the one that is checked to see if this token can be refreshed and it longer
    than 'exp', so the token might actually be expired even if it is valid to
    refresh it

    See https://github.com/davesque/django-rest-framework-simplejwt/issues/21
    """

    token = serializers.CharField()

    def validate(self, attrs):
        token = SlidingToken(attrs['token'], verify=False)

        # Check that the timestamp in the "refresh_exp" claim has not
        # passed
        token.check_exp(api_settings.SLIDING_TOKEN_REFRESH_EXP_CLAIM)

        # Update the "exp" claim
        token.set_exp()

        return {'token': text_type(token)}


class OrganizationMembershipSerializer(WritableNestedModelSerializer):
    user = StubUserSerializer()

    class Meta:
        model = OrganizationUser
        fields = ["id", "created", "is_admin", "user", "organization"]
        read_only_fields = ["id", "created", "is_admin"]
        extra_kwargs = {
            'organization': {"write_only": True}
        }


class MQTTMessageSerializer(serializers.Serializer):
    """Used with celery/mqtt test only"""
    topic = serializers.CharField()
    payload = serializers.CharField()


class PasswordResetSerializer(RestAuthPasswordResetSerializer):
    """
    Overrides the default rest_auth serializer to add a few more options
    when sending the email
    """
    def get_email_options(self):
        frontend_domain = getattr(settings, 'FRONTEND_DOMAIN')
        return {
            'domain_override': frontend_domain,
            'extra_email_context': {
                'frontend_protocol': getattr(settings, 'FRONTEND_PROTOCOL'),
                'frontend_domain': frontend_domain,
                'frontend_reset_password_confirm_path': getattr(settings, 'FRONTEND_RESET_PASSWORD_CONFIRM_PATH'),
            }
        }
