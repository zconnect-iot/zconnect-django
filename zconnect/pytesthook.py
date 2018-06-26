import os
from os.path import abspath, dirname, join

import pytest
import yaml


def pytest_addoption(parser):
    parser.addoption("--tavernize-tests", action="store_true", default=False,
        help="Run endpoint tests in tavern instead")


def pytest_runtest_setup(item):
    if isinstance(item, item.Function):
        if item.get_marker("notavern"):
            if item.config.getoption("--tavernize-tests"):
                pytest.skip("Test cannot be run using tavern")


def pytest_ignore_collect(path, config):
    if str(path).endswith("entry.py"):
        return True
    if str(path).endswith("manage.py"):
        return True


def get_test_settings():

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

    settings = dict(
        FRONTEND_PROTOCOL = 'https',
        FRONTEND_DOMAIN = 'localhost:3000',
        FRONTEND_RESET_PASSWORD_CONFIRM_PATH = 'reset',

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
        ],

        PHONENUMBER_DB_FORMAT = "INTERNATIONAL",
        PHONENUMBER_DEFAULT_REGION = "GB",
        DEBUG=True,
        ROOT_URLCONF = 'zc_test_app.urls',
        AUTH_USER_MODEL="zconnect.User",
        ENABLE_STACKSAMPLER=False,
        INSTALLED_APPS=[
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.sites",
            "django.contrib.contenttypes",
            "django.contrib.sessions",

            "zconnect",
            "zconnect.zc_billing",
            'zconnect.zc_timeseries',
            "zc_test_app",
            "organizations",
            "actstream",
            "phonenumber_field",

            "rules.apps.AutodiscoverRulesConfig",
            "rest_framework_rules",

            "rest_framework",
            "rest_framework.authtoken",
            "rest_auth",

            "rest_framework_simplejwt",
        ],

        PROJECT_TEMPLATES = [
            join(dirname(abspath(__file__)), "templates")
        ],

        TEMPLATES = [
            {
                'BACKEND': 'django.template.backends.django.DjangoTemplates',
                'DIRS': [
                    join(dirname(abspath(__file__)), "templates")
                ],
                'APP_DIRS': True,
                'OPTIONS': {
                    'context_processors': [
                        'django.contrib.auth.context_processors.auth',
                        'django.template.context_processors.debug',
                        'django.template.context_processors.i18n',
                        'django.template.context_processors.media',
                        'django.template.context_processors.static',
                        'django.template.context_processors.tz',
                        'django.contrib.messages.context_processors.messages'
                    ],
                },
            },
        ],

        # NOTE
        # Some of the tests depend on this setting
        DEFAULT_FILE_STORAGE = 'db_file_storage.storage.DatabaseFileStorage',

        MIDDLEWARE = [
            'django.middleware.security.SecurityMiddleware',
            'django.contrib.sessions.middleware.SessionMiddleware',
            'corsheaders.middleware.CorsMiddleware',
            'django.middleware.common.CommonMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
            'django.contrib.messages.middleware.MessageMiddleware',
            'django.middleware.clickjacking.XFrameOptionsMiddleware',
        ],

        ACTSTREAM_SETTINGS = {
            'USE_JSONFIELD': True,
        },

        CELERY_TASK_ALWAYS_EAGER = True,
        CELERY_TASK_EAGER_PROPAGATES = True,
        CELERY_TASK_SERIALIZER = "json",
        CELERY_RESULT_SERIALIZER='json',
        CELERY_ACCEPT_CONTENT = ['json'],

        SITE_ID=1,
        ORGS_SLUGFIELD='django_extensions.db.fields.AutoSlugField',
        # ORGS_SLUGFIELD='autoslugged.AutoSlugField',

        LOGGING=yaml.load("""
---
# 'version' is required by logging library
version: 1
disable_existing_loggers: false
# can have multiple formatters and handlers
formatters:
    default:
        (): colorlog.ColoredFormatter
        format: "{asctime:s} [{bold:s}{log_color:s}{levelname:s}{reset:s}]: ({bold:s}{name:s}:{lineno:d}{reset:s}) {message:s}"
        style: "{"
        datefmt: "%X"
        log_colors:
            DEBUG:    cyan
            INFO:     green
            WARNING:  yellow
            ERROR:    red
            CRITICAL: red,bg_white
            TRACE:    white
handlers:
    stderr:
        class: colorlog.StreamHandler
        formatter: default
loggers:
    nothing: &logref
        handlers:
            - stderr
        level: DEBUG
        propagate: false
    django:
        <<: *logref
    django.db.backends:
        <<: *logref
        level: INFO
    django.template:
        <<: *logref
        level: INFO
    rest_auth:
        <<: *logref
    rest_framework:
        <<: *logref
    rest_framework_simplejwt:
        <<: *logref
    zconnect:
        <<: *logref
    tavern:
        <<: *logref
        level: INFO
    ibmiotf:
        <<: *logref
        # level: INFO
    paho:
        <<: *logref
        level: INFO
    rules:
        <<: *logref
        # level: INFO
"""),

        AUTHENTICATION_BACKENDS=[
            "rules.permissions.ObjectPermissionBackend",
            "rest_framework_simplejwt.authentication.JWTAuthentication",
            "django.contrib.auth.backends.ModelBackend",
        ],

        REST_AUTH_TOKEN_MODEL = "rest_framework_simplejwt.tokens.SlidingToken",
        SIMPLE_JWT = {
            "AUTH_TOKEN_CLASSES": [
                "rest_framework_simplejwt.tokens.SlidingToken",
            ],
            # "ALGORITHM": "RS256",
            "SIGNING_KEY": "abc123",
            "VERIFYING_KEY": "abc123",
        },

        REST_AUTH_SERIALIZERS = {
            # NOTE
            # Look at LoginView in django rest auth to see how this is used - This
            # should take a Token (from simplejwt, above) and serializer the response
            "TOKEN_SERIALIZER": "zconnect.serializers.TokenReturnSerializer",

            # NOTE
            # This serializer does the same as the 'default' one from django rest auth
            # (but validates slightly differently, so the error response is a bit
            # different). The only advantage of using this one is that it can be set up
            # so that it doesn't actually load the user from the database, and saves a
            # db access. It also gives a better error message if a field is missing.
            "LOGIN_SERIALIZER": "zconnect.serializers.TokenWithUserObtainSerializer",
        },
        REST_AUTH_TOKEN_CREATOR = "zconnect.serializers.jwt_create_token",

        REST_FRAMEWORK={
            'DEFAULT_RENDERER_CLASSES': (
                'rest_framework.renderers.JSONRenderer',
            ),
            'DEFAULT_PERMISSION_CLASSES': [
                # 'rest_framework.permissions.IsAuthenticated',
                'rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly',
            ],
            "DEFAULT_AUTHENTICATION_CLASSES": [
                "rest_framework_simplejwt.authentication.JWTAuthentication",
                "rest_framework.authentication.SessionAuthentication",
            ],
            'DEFAULT_PAGINATION_CLASS': 'zconnect.pagination.StandardPagination',
            'PAGE_SIZE': 10,
        },

        ZCONNECT_DEVICE_SERIALIZER = "zconnect.serializers.DeviceSerializer",
        ZCONNECT_DEVICE_MODEL="zc_test_app.ZCTestDevice",
        ZCONNECT_JWT_SERIALIZER = "zconnect.serializers.JWTUserSerializer",
        ZCONNECT_USER_SERIALIZER = "zconnect.serializers.UserSerializer",
        ZCONNECT_PRODUCT_SERIALIZER = "zconnect.serializers.ProductSerializer",
        ZCONNECT_ADMIN_USER_SERIALIZER = "zconnect.serializers.UserSerializer",
        ZCONNECT_TS_AGGREGATION_ENGINE = "numpy",

        ZCONNECT_SETTINGS = {
            "SENDER_SETTINGS": {
                "cls": "zconnect.messages.IBMInterface",
            },
            "LISTENER_SETTINGS": {
                "cls": "zconnect.messages.IBMInterface",
                **DEFAULT_LISTENER_SETTINGS
            },
        },

        REDIS = {
            "connection": {
                "username": None,
                "password": None,
                "host": os.getenv('REDIS_HOST', '127.0.0.1'),
                "port": 6379,
            },
            "event_definition_evaluation_time_key": 'event_def_eval',
            # If an ev def hasn't been evaluated before, ev time will be set to
            # datetime.utcnow() + this offset.
            "event_definition_evaluation_time_clock_skew_offset": 5,
            "online_status_threshold_mins": 10,
            "event_definition_state_key": 'event_def_state',
        },

        TIME_ZONE = "UTC",
    )

    if os.getenv("DB_USE_POSTGRES"):
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                "NAME": "rtr_local_test",
                'HOST': "localhost",
                "USER": "django",
                "PASSWORD": "shae6woifaeTah7Eipax",
                # "USER": "postgres",
                # "PASSWORD": "BJQmqgHbHjFSBw",
                'ATOMIC_REQUESTS': False,
                'CONN_MAX_AGE': 0,
                "OPTIONS": {
                    "application_name": "rtr-django-composelocal",
                }
            }
        }
    else:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        }

    # DATABASES["TEST"] = DATABASES["test"] = DATABASES["default"]

    settings.update(DATABASES=DATABASES)

    return settings
