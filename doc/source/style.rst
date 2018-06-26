Coding style
============

General
-------

- Viewsets go in ``views.py``
- Serializers go in ``serializers.py``
- Filter classes go in ``filters.py``
- URL routers go in ``urls.py``
- Celery tasks go in ``tasks.py``
- Pagination classes go in ``pagination.py``
- Permissions classes go in ``permissions.py``
- Message listener action handlers/notification handlers/etc go in
  ``handlers.py``
- Models go in ``_models/<name>.py``, then should be imported in
  ``_models/__init__.py``
- Don't manually write migrations, let Django do it automatically

Models
------

- Inherit from ``zconnect.models.base`` if you want automatic ``created_at`` and
  ``updated_at`` fields

- The Device model is swappable between projects and will be set in the settings
  with ``ZCONNECT_DEVICE_MODEL``. To import it, use this pattern:

  .. code-block:: python

    from django.apps import apps
    from django.conf import settings
    Device = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)

- Validation on models should only go so far as to make sure that inconsistent
  data is not put in the database - validation on input data should be done in
  serializers.

- If you are ever expecting data to be paginated or shown in a list to a user,
  its probably a good idea to add ordering in the database or pagination doesn't
  mean anything. For example, on the location model it is done like this:

  .. code-block:: python

    class Location(ModelBase):

        timezone = models.CharField(max_length=50, blank=True)

        latitude = ...
        longitude = ...

        organization = models.CharField(max_length=50, blank=True)
        country = models.CharField(max_length=100)
        locality = models.CharField(max_length=50, blank=True)
        region = models.CharField(max_length=100)
        poboxno = models.CharField(max_length=50, blank=True)
        postalcode = models.CharField(max_length=20)
        street_address = models.CharField(max_length=100, blank=True)

        class Meta:
            ordering = ["country"]

  This means that it's ordered in the database by country - if there's 500
  locations in the database, the first page might be from a-c, the second from
  d-f, etc. Note that this is not the same as an index!

- If you are going to be querying a model from the database frequently it might
  be worth thinking about indexes. This can be done either by specifically
  adding an index to the ``Meta`` class (see `django documentation
  <https://docs.djangoproject.com/en/1.11/ref/models/options/#indexes>`__) or by
  adding ``db_index=True`` to a field definition.

  .. note::

      Indexes probably aren't needed until you have a few thousand rows in a
      table.

- When using organizations always use ``zc_billing.BilledOrganization`` instead
  of ``organizations.Organization``, it behaves identically but has extra
  functionality

Serializers
-----------

- Using a ``rest_framework.serializers.ModelSerializer`` and settings
  ``fields``/``read_only_fields`` should be enough in 90% of cases.

- Make sure the appropriate serializer is exposed based on permissions - don't
  let a user edit their own id, for example

- Filtering and permissions checking should be handled in a separate class,
  except in special situations (eg, choosing which serializer to use based on
  whether the user is an admin)

- 'Stubs' are handled by writing a different serializer with a reduced set of
  fields. If you want to stub out a related model (ie, one referenced by a
  foreign key), set this stub serializer as a field on the main serializer. A
  ``Distributor`` has a reference to a list of companies as well as to a
  location, and the serializer is like this:

  .. code-block:: python

    class StubCompanySerializer(serializers.ModelSerializer):
        class Meta:
            model = CompanyGroup
            fields = ("name", "id",)
            read_only_fields = ("name", "id",)

    class DistributorSerializer(serializers.ModelSerializer):
        companies = StubCompanySerializer(many=True, read_only=True)

        class Meta:
            model = DistributorGroup
            fields = ("name", "id", "location", "companies",)
            read_only_fields = ("name", "id",)

  Querying distributors will return something like:

  .. code-block:: json

    {
        "name": "A fake distributor",
        "location": 1,
        "companies: [
            {
                "name": "Company A",
                "id": 1
            },
            {
                "name": "Company B",
                "id": 2
            }
        ]
    }

  The location is just an ID, but because we use a stub serializer as the field
  for ``companies`` it returns the id and the name.

Viewsets
--------

- In most cases, inheriting from `rest_framework.viewsets.ModelViewSet` and
  settings the ``queryset``/``serializer_class`` should be enough to expose a
  simple endpoint.

  .. code-block:: python

    class ExampleViewSet(viewsets.ModelViewSet):
        queryset = ExampleModel.object.all()
        serializer_class = ExampleSerializer

- If you want an endpoint that can return data in the 'normal' format as well as
  the 'stubbed' format, inherit from
  ``zconnect.views.AbstractStubbableModelViewSet`` and define a
  ``normal_serializer`` and ``stub_serializer`` on it instead of
  ``serializer_class``. If the endpoint is queried with a query parameter of
  ``?stub=true`` then it will use the stub serializer instead.

  .. code-block:: python

    class ExampleViewSet(AbstractStubbableModelViewSet):
        queryset = ExampleModel.object.all()
        stub_serializer = StubExampleSerializer
        normal_serializer = ExampleSerializer

- Sometimes you need to access part of a 'nested' url, for example all event
  definitions on a product at ``/api/v3/products/1/eventdefinition``. To do
  this, also inherit from ``NestedViewSetMixin`` and use a nested router (see
  ``zconnect.urls.py`` for an example)

Filtering
~~~~~~~~~

- Some object permissions filtering is done via django-guardian - read the
  object permissions documentation for details

- To do generic filtering, the ``filter_backends`` on the viewset (or in the
  default settings) needs to include
  ``django_filters.rest_framework.DjangoFilterBackend`` and ``filter_fields``
  needs to be defined on the viewset. This will allow for automatic filtering on
  that field.

  .. code-block:: python

    class ExampleViewSet(viewsets.ModelViewSet):
        queryset = ExampleModel.object.all()
        serializer_class = ExampleSerializer

        filter_backends = [DjangoFilterBackend]
        filter_fields = ["name"]

  This will let a user filter for ExampleModel objects based on their name, for
  example ``http://example.com/example_models?name=cooldevice``

  .. todo::

    Generic wildcard filtering docs once it's in master

Ordering
~~~~~~~~

`Ordering
<http://www.django-rest-framework.org/api-guide/filtering/#orderingfilter>`__
goes alongside filtering and pagination. To make ordering work, an order has to
be set on the model Meta options or else the data returned from the ORM could be
in a random order and pagination makes no sense. This is done by setting
``ordering_fields`` and ``ordering`` on the viewset. The list of ordering fields
is what a user can ask to order results by when making a query, and the
'ordering' is what the default ordering is when returning a list of data.

.. code-block:: python

  class ExampleViewSet(viewsets.ModelViewSet):
      queryset = ExampleModel.object.all()
      serializer_class = ExampleSerializer

      ordering_fields = ["name", "age"]
      ordering = ["name"]

This will return items ordered by name by default, but will let the user order
differently if they want by passing ``?ordering=age``.

Permissions
~~~~~~~~~~~

`Permissions <www.django-rest-framework.org/api-guide/permissions/>`__ are
handled either globally through the
``REST_FRAMEWORK::DEFAULT_PERMISSION_CLASSES`` or by setting
``permision_classes``/``get_permission_classes()`` on the viewset. Look at the
object permissions documentation for more information

Nesting
~~~~~~~

For a 'nested' viewset (eg ``/devices/1/event_defs``), the 'parent' viewset
is defined as normal. All the 'nested' viewsets then need to inherit from
``zconnect.views.NestedViewSetMixinWithPermissions`` as well as
``ModelViewSet``, and specify the ``parent_viewset_class`` to indicate what it
should be querying on. Example:

.. code-block:: python

    class DeviceViewSet(NestedViewSetMixin, AbstractStubbableModelViewSet):
        _device_model = apps.get_model(settings.ZCONNECT_DEVICE_MODEL)
        queryset = _device_model.objects.all()
        pagination_class = StandardPagination

        permission_classes = [
            GroupPermissions, # subclass of DjangoObjectPermissions, to go in tandem with filter below
            permissions.IsAuthenticated,
        ]

        ...

    class EventDefinitionViewSet(NestedViewSetMixinWithPermissions, viewsets.ModelViewSet):
        queryset = EventDefinition.objects.all()
        serializer_class = EventDefinitionSerializer
        permission_classes = [IsAuthenticated]

        parent_viewset_class = DeviceViewSet

        ...

Permissions work a bit differently on nested viewsets - the 'nested' part of it
needs to be able to check whether the user has access to the 'parent'. For
example, posting an event definition to a device needs to make sure that the
user has permission to modify the device, but deleting an event definition on a
device should not require the user to have permission to delete the device.

When querying an event definition related to a specific device, the permissions
will check to see that the user has permission to change the associated parent
object (in this case, ``change_rtrdevice``).

This then needs to be hooked in in ``urls.py`` using a nested router

.. code-block:: python

    device_router = router.register(
        r'devices',
        DeviceViewSet,
        base_name="devices"
    )

    device_router.register(
        r'event_defs',
        EventDefinitionViewSet,
        parents_query_lookups=["device"],
        base_name="event_defs",
    )

``parents_query_lookups`` is how the device is looked up given an instance of an
event definition. The ``EventDefinition`` model has a foreign key reference to a
device, so we would access it like ``event_def.device``, hence ``device`` is the
``parents_query_lookups`` parameter. For nested access, use double underscore -
eg, ``timeline.event.device`` -> ``event__device``.
