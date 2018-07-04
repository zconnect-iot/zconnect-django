"""Entry point for message listener

This should not be imported other than to start the listener, because it monkey
patches gevent and starts the event loop etc.
"""
# pylint: disable=wrong-import-position,wrong-import-order
from gevent import monkey # pylint: disable=import-error
monkey.patch_all()

from psycogreen.gevent import patch_psycopg # pylint: disable=import-error
patch_psycopg()

import django
from ..listener import get_listener
from zconnect.util.profiling.stats_server import get_flask_server

django.setup(set_prefix=False)

listener = get_listener()
listener.start()

# different wsgi things use different names
app = application = get_flask_server()
