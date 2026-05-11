"""Account-level Snowflake resource bootstrap.

Creates the database, warehouse, compute pool, role, and grants the role
the privileges it needs for the platform's day-to-day operation.

The names live in `hub/config/infrastructure.yaml` and are fixed by ADR-0004
"Platform Resources". The set of resources at this layer is the single
shared baseline (one database, one role, one warehouse, one compute pool);
splitting per-env or per-tier is a separate decision tracked under ADR-0023
(proposed).

Idempotent: each SQL template uses `CREATE ... IF NOT EXISTS` so re-runs do
not destabilize an existing deployment. 

Requires ACCOUNTADMIN.
"""

import logging
from pathlib import Path

from snowflake.snowpark import Session

from hub.core.config import infra_config

logger = logging.getLogger(__name__)

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def bootstrap_account(session: Session) -> None:
    db = infra_config.database.name
    wh = infra_config.warehouse.name
    role = infra_config.role.name
    dev_pool = infra_config.compute_pools.dev
    prod_pool = infra_config.compute_pools.prod

    logger.info("Creating database %s", db)
    _execute_template(session, SQL_DIR / "infrastructure" / "create_database.sql", database_name=db)

    logger.info("Creating warehouse %s", wh)
    _execute_template(
        session,
        SQL_DIR / "infrastructure" / "create_warehouse.sql",
        warehouse_name=wh,
        warehouse_size=infra_config.warehouse.size,
        warehouse_auto_suspend=infra_config.warehouse.auto_suspend,
    )

    logger.info("Creating compute pool %s", dev_pool.name)
    _execute_template(
        session,
        SQL_DIR / "infrastructure" / "create_compute_pool.sql",
        pool_name=dev_pool.name,
        min_nodes=dev_pool.min_nodes,
        max_nodes=dev_pool.max_nodes,
        instance_family=dev_pool.instance_family,
        auto_suspend_secs=dev_pool.auto_suspend_secs,
        comment="Shared compute pool for dev and staging workloads.",
    )

    if prod_pool.name != dev_pool.name:
        logger.info("Creating compute pool %s", prod_pool.name)
        _execute_template(
            session,
            SQL_DIR / "infrastructure" / "create_compute_pool.sql",
            pool_name=prod_pool.name,
            min_nodes=prod_pool.min_nodes,
            max_nodes=prod_pool.max_nodes,
            instance_family=prod_pool.instance_family,
            auto_suspend_secs=prod_pool.auto_suspend_secs,
            comment="Compute pool for production workloads.",
        )

    logger.info("Creating role %s", role)
    _execute_template(session, SQL_DIR / "infrastructure" / "create_role.sql", role_name=role)

    # Place the new role under SYSADMIN. SYSADMIN is granted to ACCOUNTADMIN
    # by default, so the connecting ACCOUNTADMIN session inherits this role's
    # ownership-derived privileges via the hierarchy. Without this, the
    # GRANT OWNERSHIP below transfers DB ownership away from ACCOUNTADMIN's
    # reach and subsequent CREATE SCHEMA in the same session fails.
    logger.info("Placing %s under SYSADMIN", role)
    session.sql(f"GRANT ROLE {role} TO ROLE SYSADMIN").collect()

    logger.info("Granting database privileges to %s", role)
    _execute_template(session, SQL_DIR / "grants" / "grant_database_permissions.sql", database_name=db, role_name=role)
    _execute_template(session, SQL_DIR / "grants" / "grant_object_creation.sql", database_name=db, role_name=role)
    _execute_template(session, SQL_DIR / "grants" / "grant_object_privileges.sql", database_name=db, role_name=role)

    logger.info("Granting warehouse access to %s", role)
    _execute_template(session, SQL_DIR / "grants" / "grant_warehouse_access.sql", warehouse_name=wh, role_name=role)

    logger.info("Granting compute pool access to %s", role)
    pool_grant_sql = SQL_DIR / "grants" / "grant_compute_pool_access.sql"
    _execute_template(session, pool_grant_sql, pool_name=dev_pool.name, role_name=role)
    if prod_pool.name != dev_pool.name:
        _execute_template(session, pool_grant_sql, pool_name=prod_pool.name, role_name=role)

    logger.info("Granting task execution privileges to %s", role)
    _execute_template(session, SQL_DIR / "grants" / "grant_task_privileges.sql", role_name=role)


def _execute_template(session: Session, path: Path, **params: object) -> None:
    sql = path.read_text(encoding="utf-8").format(**params)
    for statement in (s.strip() for s in sql.split(";")):
        if statement:
            session.sql(statement).collect()
