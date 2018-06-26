Authentication
==============

.. note::

    At the time of writing we only have the login endpoint exposed, not logging
    out or refreshing tokens or anything. This can be done but it's not done
    yet

Authentication is specified in ``AUTHENTICATION_BACKENDS`` in the settings.
Read `Django docs
<https://docs.djangoproject.com/en/2.0/ref/settings/#std:setting-AUTHENTICATION_BACKENDS>`__
for details on how authentication backends work. This is just a list of classes
which are all used to check if a user is authenticated, each of which has it's
own method of checking. The two we have are:

1. Default Django ``django.contrib.auth.backends.ModelBackend`` - checks username
   and password passed in a basic auth header
2. JWT authentication - checks to see if a JWT is passed as a bearer token in
   the auth header

JWT authentication is handled though a couple of other libraries:

- `django-rest-auth <https://django-rest-auth.readthedocs.io/en/latest/>`__
  provides the urls/viewsets for forgotten passwords etc
- `djangorestframework-simplejwt
  <https://github.com/davesque/django-rest-framework-simplejwt/>`__ is used to
  create JWTs for rest-auth

Why not use django-rest-framework-jwt?
--------------------------------------

- It is VERY tied into using the PyJWT library and the interface to it is spread
  across a lot of different files so it's hard to switch out. There are various
  problems with PyJWT but the main one is that if we want to use JWKS at any
  point, it isn't supported

- simplejwt has a helper that lets you use a 'fake' user based on the
  information in the JWT to avoid querying the database on every login, like it
  was done in bigbird

- It was easier to create/add custom fields to the JWT using simplejwt

- simplejwt does have all the same endpoints for refreshing tokens etc

- simplejwt has an optional token blacklist that we can enable in future if
  needed

- simplejwt has support for sliding tokens, which we don't use now but we can in
  future if we want to

- The code in simplejwt seemed a bit more concise/easier to understand

How it works
------------

There is some documentation in ``common.py`` to explain some of this stuff as
well.

The endpoints work in a similar fashion to all the other viewsets, but they are
backed by the django token which we never directly interface with

Logging in
~~~~~~~~~~

1. Input is validated using ``REST_AUTH_SERIALIZERS::LOGIN_SERIALIZER`` - this
   validates the input data to make sure that it is in the correct format to
   login. This is just:
 
   .. code-block:: json
 
     {
         "username": "joeseed@zoetrope.io",
         "password": "test_password",
     }
 
   There are a couple of reasons why we use ``username`` rather than ``email``, the
   main one being that the default django ``ModelBackend`` only works with
   ``username``. Seeing as we never use the username anywhere and just use an
   email, we're just going to make sure that the username is always the same as
   the email.
 
2. ``django-rest-auth`` creates a token *object* of type ``REST_AUTH_TOKEN_MODEL``,
   using ``REST_AUTH_TOKEN_CREATOR``, and then serializers it back to the user
   with ``REST_AUTH_SERIALIZERS::TOKEN_SERIALIZER``.

These both use functionality from simplejwt, extended by us.

.. note::

    django-rest-auth has some functionality to let you use
    django-rest-framework-jwt to create JWTs to use as tokens, but it's very
    rudimentary and doesn't really do everything we want - this is all
    implemented outside of those libraries

Refreshing token
~~~~~~~~~~~~~~~~

If you post to ``/.../refresh`` with JWT auth (ie, with the header
``Authorization: Bearer abc123`` it will return a new ``token`` in the body.

Extra unused functionality
--------------------------

The simplejwt library has some extra stuff which we aren't using

- The way we use the tokens is called a 'sliding' token in simplejwt. It is
  possible to change this so we actually have a real access token and a refresh
  token, but to keep parity with the old api it just uses these 'sliding'
  tokens

- There is a blacklist backend which can be enabled by a setting which allows
  you to blacklist jwts or users via the admin interface - this is currently
  disabled.

- There is an unused viewset to verify a token - this just checks the signature,
  doesn't check what the token is actually used for.
