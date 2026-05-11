import logging

from snowflake.snowpark import Session
from snowflake.snowpark.exceptions import SnowparkSQLException

logging.getLogger().setLevel(logging.INFO)

logger = logging.getLogger(__name__)


def try_run_query(session: Session, query: str) -> bool:
    """
    Try to execute a SQL query and return whether it succeeded.

    This function attempts to execute a SQL query and returns True if successful,
    False if it fails with certain error codes. It re-raises the exception for
    critical errors (error code 1003).

    Args:
        session (Session): Snowflake session object
        query (str): SQL query to execute

    Returns:
        bool: True if query executed successfully, False if it failed gracefully

    Raises:
        SnowparkSQLException: If the query fails with error code 1003 (critical error)
    """
    try:
        session.sql(query).collect()
        return True
    except SnowparkSQLException as e:
        if e.sql_error_code == 1003:
            raise
        return False
