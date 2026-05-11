"""SQL execution utilities for template-based database operations."""

import logging
from pathlib import Path

from snowflake.snowpark import Session

logger = logging.getLogger(__name__)


def execute_sql_file(session: Session, sql_file_path: str | Path, **params) -> None:
    """Execute SQL file with parameter substitution.

    Args:
        session: Snowflake session
        sql_file_path: Path to SQL file (relative to project root or absolute)
        **params: Parameters to substitute in SQL template (e.g., database="MYDB", schema="MYSCHEMA")

    Example:
        >>> execute_sql_file(
        ...     session, "scripts/sql/inference_tables.sql", database="OSS_SF_MLOPS", schema="PUDO_DEV"
        ... )
    """
    sql_file = Path(sql_file_path)

    # If relative path, resolve from project root
    if not sql_file.is_absolute():
        # Assume we're running from project root or scripts/
        project_root = Path(__file__).parent.parent.parent.parent
        sql_file = project_root / sql_file

    if not sql_file.exists():
        msg = f"SQL file not found: {sql_file}"
        raise FileNotFoundError(msg)

    logger.info(f"Executing SQL file: {sql_file}")

    # Read SQL file
    sql_content = sql_file.read_text()

    # Replace parameters
    for key, value in params.items():
        placeholder = f"{{{key}}}"
        sql_content = sql_content.replace(placeholder, str(value))

    # Split by statement (simple approach: split on ';' followed by newline)
    statements = [stmt.strip() for stmt in sql_content.split(";") if stmt.strip()]

    # Execute each statement
    for i, statement in enumerate(statements, 1):
        logger.debug(f"Executing statement {i}/{len(statements)}")
        try:
            session.sql(statement).collect()
        except Exception as e:
            logger.error(f"Error executing statement {i}: {e}")
            logger.error(f"Statement: {statement[:200]}...")
            raise

    logger.info(f"Successfully executed {len(statements)} SQL statements")


def test_connection(session: Session) -> str:
    """Test database connection and return Snowflake version.

    Args:
        session: Snowflake session

    Returns:
        str: Current Snowflake version
    """
    result = session.sql("SELECT CURRENT_VERSION()").collect()
    return result[0][0] if result else "Unknown"
