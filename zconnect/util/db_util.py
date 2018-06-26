import contextlib
import logging

from django.conf import settings
from django.db import OperationalError, connection, connections, reset_queries
from sqlparse import format as fmt

logger = logging.getLogger(__name__)


def check_db():
    try:
        connections['default'].cursor()
    except OperationalError:
        return False
    return True


def format_sql(query):
    return fmt(str(query), reindent=True, keyword_case='upper')


def format_query_sql(queryset):
    return format_sql(queryset.query)


@contextlib.contextmanager
def log_n_queries():
    """Log the number of database queries made inside context manager

    Requires DEBUG to be set to True
    """
    if not settings.DEBUG:
        logger.debug("DEBUG is False, will not count queries")
        yield
    else:
        try:
            reset_queries()
            yield
        finally:
            logger.info("%s queries performed", len(connection.queries))
