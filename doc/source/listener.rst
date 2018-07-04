Starting the message listener
-----------------------------

The message listener starts a separate thread in the background to listen for
messages and then the main thread will just sleep. When a message comes in, the
appropriate callback will be called.

The class that does this, ``MessageListener``, inherits from
``threading.Thread`` by default, so one way to start this is to have an entry
point like this:

.. code-block:: python

    import django
    django.setup(set_prefix=False)

    from .listener import get_listener
    listener = get_listener()
    listener.start()
    listener.join()

This will set up django and then start the message listener, then just wait for
messages to come in.

If you want to enable the profiling in the background, this uses gevent so the
entry point needs to be a bit different:

.. code-block:: python

    from gevent import monkey
    monkey.patch_all()

    from psycogreen.gevent import patch_psycopg
    patch_psycopg()

    import django
    from .listener import get_listener
    from zconnect.util.profiling.stats_server import get_flask_server

    django.setup(set_prefix=False)

    listener = get_listener()
    listener.start()

    app = application = get_flask_server()

This will:

1. monkey patch modules using gevent
2. monkey patch psycopg2 db adapter so it works with gevent
3. setup django and start the listener
4. get the server to start serving performance data

This can be start using a wsgi server of your choice. For uwsgi, the config file
would look something like this:

.. code-block:: ini

    [uwsgi]
    http-socket    = :12345
    plugin    = python3,gevent
    mount = /=my_module.message_entry:application
    gevent = 100
    # gevent-monkey-patch = true

Note that we don't monkey patch in the uwsgi config because we're already doing
it in the entry point code. This will host the stack sampler on port 12345.

Examples of both of these are in the ``zconnect/_messages/entry`` folder
