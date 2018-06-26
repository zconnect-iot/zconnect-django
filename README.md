# ZConnect Django

semi-reusable django app to provide basic zconnect functionality

## Required settings

zconnect-django is semi-reusable in that it expects external libraries to be configured in certain ways for it to behave properly, as well as having some settings which just need to be set for it to behave properly

    AUTH_PASSWORD_VALIDATORS = [
        {
            'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
        },
        {
            'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        },
        {
            'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
        },
        {
            'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
        },
    ]

Validating passwords

    PHONENUMBER_DB_FORMAT = "INTERNATIONAL",
    PHONENUMBER_DEFAULT_REGION = "GB",

Validating phone numbers for sending notifications

    INSTALLED_APPS=[
        "zconnect",
        "zconnect.zc_billing",
        'zconnect.zc_timeseries',

        "organizations",
        "actstream",
        "phonenumber_field",
        "rules.apps.AutodiscoverRulesConfig",
        "rest_framework_rules",
        "rest_framework",
        "rest_framework.authtoken",
        "rest_auth",
        "rest_framework_simplejwt",
    ]

all of these packages are required

    DEFAULT_FILE_STORAGE = 'db_file_storage.storage.DatabaseFileStorage',

Storing files in the database (eg, logos for companies)

    ACTSTREAM_SETTINGS = {
        'USE_JSONFIELD': True,
    },

Need to use the special JSONField

    ORGS_SLUGFIELD='django_extensions.db.fields.AutoSlugField',

Needed to make django-organizations generate slugs for organizations properly

    AUTHENTICATION_BACKENDS=[
        "rules.permissions.ObjectPermissionBackend",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "django.contrib.auth.backends.ModelBackend",
    ],

*Minimal* settings to make the auth work - use rules to check permissions first, then jwt auth (which should only be used to authorize access to endpoints), then use the django model backend to check user permissions if neither of those work.

    REST_AUTH_TOKEN_MODEL = "rest_framework_simplejwt.tokens.SlidingToken",
    SIMPLE_JWT = {
        "AUTH_TOKEN_CLASSES": [
            "rest_framework_simplejwt.tokens.SlidingToken",
        ],
    }
    REST_AUTH_SERIALIZERS = {
        "TOKEN_SERIALIZER": "zconnect.serializers.TokenReturnSerializer",
        "LOGIN_SERIALIZER": "zconnect.serializers.TokenWithUserObtainSerializer",
    },
    REST_AUTH_TOKEN_CREATOR = "zconnect.serializers.jwt_create_token",

Used for generting JWTs for authorization

    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "rest_framework_simplejwt.authentication.JWTAuthentication",
            "rest_framework.authentication.SessionAuthentication",
        ],
        'DEFAULT_PAGINATION_CLASS': 'zconnect.pagination.StandardPagination',
    },

There are lots of other rest framework settings, but these ones are required. consider settings `DEFAULT_PERMISSION_CLASSES` to contain `rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly`

    ZCONNECT_DEVICE_MODEL="zconnect.Device",

Device model. You will almost always want to override this because it's hard work to switch out later.

    TIME_ZONE = "UTC",

Should be set to avoid timezone issues

    REDIS = {
        "connection": {
            "username": None,
            "password": None,
            "host": os.getenv('REDIS_HOST', '127.0.0.1'),
            "port": 6379,
        },
        "event_definition_evaluation_time_key": 'event_def_eval',
        "event_definition_evaluation_time_clock_skew_offset": 5,
        "online_status_threshold_mins": 10,
        "event_definition_state_key": 'event_def_state',
    },

Currently zconnect uses redis for the celery queue backend - these settings are needed so it can connect

### zconnect specific settings

    DEFAULT_LISTENER_SETTINGS = {
        "worker_events_rate_limits": {
            "event": 100,
            "fw_update_complete": 100,
            "gateway_new_client": 100,
            "init_wifi_success": 100,
            "ir_receive_codes": 100,
            "ir_receive_codes_complete": 100,
            "local_ip": 100,
            "manual_status": 100,
            "periodic": 1000,
            "settings": 100,
            "version": 100,
            # for testing
            "rate_limiter_event": 1,
        },
        "rate_limit_period": 600,
    }

    ZCONNECT_SETTINGS = {
        "SENDER_SETTINGS": {
            "cls": "zconnect.messages.IBMInterface",
        },
        "LISTENER_SETTINGS": {
            "cls": "zconnect.messages.IBMInterface",
            **DEFAULT_LISTENER_SETTINGS
        },
    },

Main zconnect settings dict. Currently just has the settings for listener and sender.

#### To be fixed

https://code.zoetrope.io/zconnect/zconnect-django/issues/95

These should be moved to `ZCONNECT_SETTINGS` in future

    FRONTEND_PROTOCOL = 'https',
    FRONTEND_DOMAIN = 'localhost:3000',
    FRONTEND_RESET_PASSWORD_CONFIRM_PATH = 'reset',

Used when sending password reset emails to say where to redirect the user to

    ZCONNECT_DEVICE_SERIALIZER = "zconnect.serializers.DeviceSerializer",
    ZCONNECT_JWT_SERIALIZER = "zconnect.serializers.JWTUserSerializer",
    ZCONNECT_USER_SERIALIZER = "zconnect.serializers.UserSerializer",
    ZCONNECT_PRODUCT_SERIALIZER = "zconnect.serializers.ProductSerializer",
    ZCONNECT_ADMIN_USER_SERIALIZER = "zconnect.serializers.UserSerializer",

Various serializers might need to add extra fields if you have extra fields in the JWT etc. override these settings if that is the case

    ZCONNECT_TS_AGGREGATION_ENGINE = "numpy",

How to run timeseries aggregations. Currently this can only be numpy.

## Running tests

**TODO** figure out a nice way to use 'test' settings in this kind of app.

Should be like this:

1. `pip install -e .[tests]`
2. `tox` or `pytest`
