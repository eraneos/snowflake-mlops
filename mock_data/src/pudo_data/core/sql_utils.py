"""SQL execution utilities for template-based database operations."""

import logging
from pathlib import Path

from snowflake.snowpark import Session

logger = logging.getLogger(__name__)


def execute_sql_file(session: Session, sql_file_path: str | Path, **params) -> None:
    """Execute a SQL file with `{key}` placeholder substitution.

    Relative paths resolve against `mock_data/` (this file lives at
    `mock_data/src/pudo_data/core/sql_utils.py`).
    """
    sql_file = Path(sql_file_path)

    if not sql_file.is_absolute():
        mock_data_root = Path(__file__).resolve().parents[3]
        sql_file = mock_data_root / sql_file

    if not sql_file.exists():
        msg = f"SQL file not found: {sql_file}"
        raise FileNotFoundError(msg)

    logger.info("Executing SQL file: %s", sql_file)

    sql_content = sql_file.read_text()
    for key, value in params.items():
        sql_content = sql_content.replace(f"{{{key}}}", str(value))

    statements = [stmt.strip() for stmt in sql_content.split(";") if stmt.strip()]
    for i, statement in enumerate(statements, 1):
        logger.debug("Executing statement %d/%d", i, len(statements))
        try:
            session.sql(statement).collect()
        except Exception as e:
            logger.error("Error executing statement %d: %s", i, e)
            logger.error("Statement: %s...", statement[:200])
            raise

    logger.info("Executed %d SQL statements", len(statements))


def test_connection(session: Session) -> str:
    result = session.sql("SELECT CURRENT_VERSION()").collect()
    return result[0][0] if result else "Unknown"
