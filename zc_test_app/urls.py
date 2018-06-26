""" The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
"""
# Django imports
from django.conf.urls import include, url
from django.contrib import admin
from rest_auth.views import (
    LoginView, LogoutView, PasswordChangeView,
    PasswordResetConfirmView
)

##############################
# For this app
##############################

from zconnect.views import StackSamplerView, CeleryMQTTTestViewSet


# TODO
# http data endpoint
# Might have to be a basic function-type view because it doesn't correspond
# directly to the Device model


##############################
# All
##############################

urlpatterns = [
    # enable the admin interface
    url(r'^admin/', admin.site.urls),

    url(r'^stats/stacksampler', StackSamplerView.as_view()),

    url(r'^api/v3/auth/password/reset/confirm/$', PasswordResetConfirmView.as_view(),
        name='rest_password_reset_confirm'),

    url(r'^api/v3/auth/login/$', LoginView.as_view(), name='rest_login'),

    # URLs that require a user to be logged in with a valid session / token.
    url(r'^api/v3/auth/logout/$', LogoutView.as_view(), name='rest_logout'),

    url(r'^api/v3/auth/password/change/$', PasswordChangeView.as_view(),
        name='rest_password_change'),

    # Rest Auth requires auth urls. If we remove this, then we'll get an error
    # around NoReverseMatch
    # TODO: Work out how to avoid external access to these URLs if possible
    url(r'^', include('django.contrib.auth.urls')),

    url(r'^api/v3/', include('zconnect.urls')),
    url(r'^api/v3/', include('zconnect.zc_billing.urls')),

    url(r'^celerymqtttest/', CeleryMQTTTestViewSet.as_view({'post': 'create'})),
    # For django-db-file-storage:
    url(r'^files/', include('db_file_storage.urls')),
]

