Object level permissions
========================

Permissions to access endpoints and specific models are handled by a couple of
different libraries:

- Default django `permissions
  <https://docs.djangoproject.com/en/2.0/ref/contrib/auth/#permission-model/>`__
  are used as the 'base' permission class
- `django-guardian <https://django-guardian.readthedocs.io/en/stable/>`__
  handles the object level permissions - this extends the base permission class
  functionality with the ability to store the permissions for a specific object
  id
- django-rest-framework `filtering
  <http://www.django-rest-framework.org/api-guide/filtering/#djangoobjectpermissionsfilter>`__
  and `permissions
  <http://www.django-rest-framework.org/api-guide/permissions/#djangoobjectpermissions>`__
  are used to check the permissions in the database and filter results based on
  the current user (which can be an anonymous user!).
- `django-rules <https://github.com/dfunckt/django-rules>`__ is used to handle
  object level permissions for objects owned by organizations.

These are the steps taken on the backend when somebody accesses an endpoint with
model level permissions:

1. Loop through ``AUTHENTICATION_BACKENDS`` to see if the request is authenticated
   or not - if not, it will use an anonymous user to continue to the next stage.
2. Check the permission classes to see if the user has permission to access that
   endpoint. This is normally in ``REST_FRAMEWORK::DEFAULT_PERMISSION_CLASSES`` in
   the settings, but this can be overridden on each viewset - to get object
   level permissions working properly, ``zconnect.permissions.GroupPermissions``
   needs to be used (ALWAYS in tandem with
   ``rest_framework.permissions.IsAuthenticated``).
3. Filter the results based on what the user is allowed to see and query
   parameters. This is done via filters on the viewset, normally in
   ``REST_FRAMEWORK::DEFAULT_FILTER_BACKENDS``. Like above, to get object
   permissions filtering working this needs to include
   ``rest_framework.filters.DjangoObjectPermissionsFilter``. It is normally useful
   to also add ``django_filters.rest_framework.DjangoFilterBackend`` to allow for
   other filtering.

Permissions (step 2) is done in 2 different stages:

1. Permission to access the endpoint (``has_perm`` on the permission class). This
   is done based on the HTTP verb used.
2. Permission to access a specific object (only when trying to access a specific
   object - eg ``/api/v3/devices/123`` (``has_object_perm`` on the permission class)

A permission class might pass step 1 for a user, but then fail step 2.

.. note::

    Authentication backends are PERMISSIVE - django will loop through them until
    it finds one that logs in a user successfully, or uses an anonymous user.
    Permission classes are RESTRICTIVE - ALL permissions checks need to pass to
    allow a user to access the endpoint. Filters are 'transparent' - they will
    filter the queryset based on object level permissions, so a list might end
    up empty even if there are multiple items in the database.

There is a difference between a 'soft' failure and a 'hard' failure when doing
authentication. A 'soft' failure is when the authentication backend cannot tell
whether a user should be allowed to or not and continues to the next backend, a
'hard' failure is when it can categorically say that the user should not be
allowed to do whatever they're trying to do. Example:

.. code-block:: python

    from rest_framework import permissions

    class UserNotCalledJoe(permissions.BasePermission):

        def has_perm(self, request, view):
            if request.user:
                if request.user.first_name == "Joe":
                    # Should not have permissions - hard failure
                    raise PermissionDeniedError()
                else:
                    # Success
                    return True

            # Don't know, we don't have a user, soft failure
            return False

.. todo::

    Is this correct? check docs when we have internet

Group permissions and django-guardian
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

django-guardian uses django's _group_ permissions to figure out whether a user
is allowed to access an endpoint or not. There will probably not be many groups
in each project, just something like "admin", "user", etc.

``GroupPermissions`` has a map of HTTP verb -> permission like this:

.. code-block:: python

    perms_map = {
        'GET': [],
        'OPTIONS': [],
        'HEAD': [],

        'POST': ['%(app_label)s.add_%(model_name)s'],

        'PUT': ['%(app_label)s.change_%(model_name)s'],
        'PATCH': ['%(app_label)s.change_%(model_name)s'],

        'DELETE': ['%(app_label)s.delete_%(model_name)s'],
    }

When checking ``has_perm``, it checks that the user or any of the groups that
the user is in has permission to do the associated action. For example, trying
to delete a device would require ``zconnect.delete_device``

.. todo::

    Does this raise a hard error or continue?

All these permissions are stored in the database, and each user (or group) has a
few rows in another table that just stored which permissions they have.
django-guardian then does some big complicated queries to see if the user or any
of their groups has the desired permission.

Organization permissions and django-rules
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Because we use Organizations as a base building block, it's also useful to have
permissions based on that. There is likely to be a lot of organizations per
project and lots of users, and storing each permission for each
user/organization would take up a lot of space (and reimplement much of
django-guardian for a slightly different purpose).


For this reason all organization level permission checking is done using
django-rules, which lets you essentially specify a function for each permission
rather than storing anything in the database. These rules should be placed in a
file called ``rules.py`` which will then be auto-loaded if
``rules.apps.AutodiscoverRulesConfig`` is placed in ``INSTALLED_APPS``.

Simple example that restricts changing to devices to all users who are called
Joe, but lets anyone who is a member of any of the organizations that the device
belongs to view it:

.. code-block:: python

    import rules

    def is_user_joe(user, obj):
        return user.first_name == "Joe"

    def is_in_org(user, obj):
        return any(i in obj.orgs.all() for i in user.orgs.all())

    rules.add_perm("zconnect.view_device", is_in_org)
    rules.add_perm("zconnect.change_device", is_user_joe)

.. note::

    If you write an inefficient function to check permissions it can cause
    a lot of queries and slow down permissions checking, try to reduce the
    number of queries done in the function

These tend to be project-specific so there are no built-in rules in zconnect

Accessing an endpoint
---------------------

The ``/api/v3/devices/`` endpoint goes to ``DeviceViewSet``:

.. code-block:: python

    class DeviceViewSet(NestedViewSetMixin, AbstractStubbableModelViewSet):
        _device_model = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)
        queryset = _device_model.objects.all()

        permission_classes = [
            GroupPermissions,
            permissions.IsAuthenticated,
        ]

        filter_backends = [
            DjangoFilterBackend,
            # This uses django-guardian permissions
            # filters.DjangoObjectPermissionsFilter,
            OrganizationObjectPermissionsFilter,
        ]
        filter_fields = ["name"]

        # ... other fields

This has both permission classes so a user has to be authenticated (not
anonymous) and must have permission to view the device model. ``filter_fields`` is
used by the ``DjangoFilterBackend``, and is separate to the object permissions
filtering.

.. warning::

    By default, Django will create permissions for objects - ``add``, ``change``,
    and ``delete``. It will NOT create a ``view`` permission! If you look at
    ``GroupPermissions`` in zconnect/permissions, it will allow ANYONE to do a
    ``GET`` on the endpoint. ALWAYS use ``GroupPermissions`` with an authentication
    backend that ensures that the user is logged in.

If our device model is called ``FakeDevice``, these permissions will be called
something like ``change_fakedevice``, ``delete_fakedevice``, etc (These are also
used in ``GroupPermissions``). These permissions will be created in the database
automatically, and permission to view the devices should be given globally to
users.

For the following scenarios, we have:

- 1 device with id ``1`` which belongs to a org ``test_org``
- 1 user called ``fredbloggs`` who is in no orgs but has the ``change_fakedevice``
  permission
- 1 user called ``joeseed``, who also has the 'global'
  ``change_fakedevice`` permission and is ALSO in ``test_org`` which has the OBJECT
  LEVEL ``change_fakedevice`` permission on the device.
- A function using django-rules that allows members of organizations that the
  device is also a member of to edit and view them

.. note::

    'Global' permissions are different from the object level permissions and the
    django-guardian documentation is not very good about explaining - I think by
    default django-guardian might use global permissions, which means some of
    the expected behaviour in this documentation might be slightly wrong

We are assuming these tests are run with an authenticated user - step 1 in the
steps at the top of the page for all these is not shown here.

Listing all devices
~~~~~~~~~~~~~~~~~~~

If ``fredbloggs`` queries ``/api/v3/devices/``:

2. No special permissions are required to do a ``GET``, so it continues to the
   next stage
3. The queryset is filtered based on permissions - because ``fredbloggs`` is not
   in the right org and hence has no permissions, an empty list is returned.

If ``joeseed`` queries ``/api/v3/devices/`` :

2. As above
3. ``joeseed`` is in the same org as the device, so it will return a list with a
   single device in it.

Getting a specific device
~~~~~~~~~~~~~~~~~~~~~~~~~

If ``fredbloggs`` queries ``/api/v3/devices/1``:

2. No special permissions are required to do a ``GET``, but object level
   permissions ARE required to try and access a particular object - return 403.

If ``joeseed`` queries ``/api/v3/devices/`` :

2. ``joeseed`` has permissions to access this specific object, so return it. (No
   filtering because we're getting a specific device.)

Modifying a device
~~~~~~~~~~~~~~~~~~

If ``fredbloggs`` does a ``PUT`` to ``/api/v3/devices/1``:

2. ``fredbloggs`` has the global ``change_fakedevice`` permission, but does not have
   permission to do it on this specific device. At the time of writing, this
   means that ``GroupPermissions`` will let them do the ``PUT``, but then the
   ``OrganizationObjectPermissionsFilter`` will filter out the specific device and a 404
   will be returned (as if this device did not exist).

If ``joeseed`` does a ``PUT`` to ``/api/v3/devices/1``:

2. ``joeseed`` has the ``change_fakedevice`` permission to access this specific
   object, so modify it and return the updated object.

Similar logic is followed when trying to delete a device, except it uses the
``delete_fakedevice`` permission instead

Creating a new device
~~~~~~~~~~~~~~~~~~~~~

Because we are creating a new device, object level permissions do not apply. If
``fredbloggs`` or ``joeseed`` post to ``/api/v3/devices/``, they have the global
``add_fakedevice`` permission, and the data they post is correct, then they will
both successfully create a device (at the time of writing).
