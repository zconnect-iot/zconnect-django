"""Entry point for message listener

This just starts a thread to run in the background
"""

import django
from ..listener import get_listener

django.setup(set_prefix=False)

listener = get_listener()
listener.start()
listener.join()
