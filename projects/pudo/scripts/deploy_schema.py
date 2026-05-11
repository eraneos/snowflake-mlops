"""Deploy the PUDO project schema with all required infrastructure.

**FOUNDATION SCRIPT** - Run this first before any other deployment scripts.

This script creates the project schema (`PUDO_<ENV>` per ADR-0004) with:
- All stages (TRAINING_DAG_STAGE, TRAINING_JOB_STAGE, INFERENCE_DAG_STAGE)
- Inference pipeline table: PREDICTIONS
- Views: PUDO_ALERTS, INFERENCE_METRICS

Note: Core PUDO tables (PUDO_REFERENCE, PARCELS, DELIVERY_ATTEMPTS, PUDO_OCCUPANCY)
and the simulation-state table DATA_GENERATION_LOG live in SHARED_DATA, created by
the mock-data seed (`make -C mock_data seed-shared-data`). The SHARED_DATA schema
itself is created by hub bootstrap (`make -C hub deploy-infra`).

Usage:
    uv run python scripts/deploy_schema.py
    uv run python scripts/deploy_schema.py --dry-run

Prerequisite chain:
- deploy_feature_store.py (requires schema)
- deploy_training_dag.py (requires schema + stages)
- deploy_inference_dag.py (requires schema + stages + tables)
"""

import argparse
import logging
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from pudo.core.config.infrastructure import config as infra_config
from pudo.core.environment import detect_environment, get_project_schema
from pudo.core.snowflake_session import get_session
from pudo.core.sql_utils import execute_sql_file, test_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
console = Console()


def deploy_schema(*, dry_run: bool = False) -> None:
    """Deploy complete schema with all tables and stages.

    Args:
        dry_run: If True, validate but don't make changes
    """
    console.print(Panel.fit("[bold blue]Deploy Project Schema[/bold blue]", border_style="blue"))

    # Get configuration
    # Import ML configs to get stage names
    from pudo.core.config.ml.inference import config as inference_config
    from pudo.core.config.ml.training import config as training_config

    database = infra_config.database.name
    environment = detect_environment()
    schema = get_project_schema(environment)

    # Extract stage names from ML configs
    training_dag_stage = training_config.pipeline.dag_stage
    training_job_stage = training_config.pipeline.job_stage
    inference_dag_stage = inference_config.pipeline.dag_stage

    console.print(f"\n[cyan]Environment:[/cyan] {environment.upper()}")
    console.print(f"[cyan]Database:[/cyan] {database}")
    console.print(f"[cyan]Schema:[/cyan] {schema}")
    console.print(f"\n[yellow]Note:[/yellow] Creating complete schema in [bold]{database}.{schema}[/bold]")

    sql_file = Path(__file__).resolve().parent / "sql" / "inference_tables.sql"

    if dry_run:
        console.print("\n[yellow]DRY RUN MODE - No changes will be made[/yellow]")
        console.print("\n[yellow]Would execute:[/yellow]")
        console.print("  1. Create schema if not exists")
        console.print(f"  2. Execute {sql_file}")
        console.print(f"  3. Create {training_dag_stage}, {training_job_stage}, and {inference_dag_stage}")
        console.print("\n[green]Dry run complete[/green]")
        return

    # Get session
    session = get_session()

    # Test connection
    console.print("\n[bold]Testing connection...[/bold]")
    version = test_connection(session)
    console.print(f"✅ Connected to Snowflake version: {version}")

    # Create schema
    console.print(f"\n[bold]Creating schema {schema}...[/bold]")
    session.sql(f"CREATE SCHEMA IF NOT EXISTS {database}.{schema}").collect()
    session.sql(f"USE SCHEMA {database}.{schema}").collect()
    console.print(f"✅ Schema {schema} ready")

    # Note: Core PUDO tables should exist in SHARED_DATA schema (owned by hub bootstrap)
    # We only create inference tables in the project schema
    console.print("\n[yellow]Note:[/yellow] Core PUDO tables expected in SHARED_DATA schema")
    console.print("[yellow]If missing, run: make -C mock_data seed-shared-data[/yellow]")

    # Execute inference tables SQL
    console.print("\n[bold]Creating inference pipeline tables...[/bold]")
    execute_sql_file(session, sql_file, database=database, schema=schema)
    console.print("✅ Inference tables created")

    # Create stages
    console.print("\n[bold]Creating stages...[/bold]")
    session.sql(f"CREATE STAGE IF NOT EXISTS {database}.{schema}.{training_dag_stage}").collect()
    session.sql(f"CREATE STAGE IF NOT EXISTS {database}.{schema}.{training_job_stage}").collect()
    session.sql(f"CREATE STAGE IF NOT EXISTS {database}.{schema}.{inference_dag_stage}").collect()
    console.print("✅ Stages created")

    # Display summary
    console.print("\n[bold green]✅ Schema deployment complete![/bold green]")
    console.print(f"\n[bold]Created in {database}.{schema}:[/bold]")
    console.print("  • Inference table: PREDICTIONS")
    console.print("  • Views: PUDO_ALERTS, INFERENCE_METRICS")
    console.print(f"  • Stages: {training_dag_stage}, {training_job_stage}, {inference_dag_stage}")
    console.print(f"\n[bold]Shared data (from {database}.SHARED_DATA):[/bold]")
    console.print("  • Core tables: PUDO_REFERENCE, PARCELS, DELIVERY_ATTEMPTS, PUDO_OCCUPANCY")
    console.print("  • Simulation state: DATA_GENERATION_LOG")

    console.print("\n[bold]Next steps:[/bold]")
    console.print("[yellow]Foundation complete! Now deploy domain-specific components:[/yellow]")
    console.print("\n1. Deploy feature store:")
    console.print("   [cyan]make deploy-feature-store[/cyan]")
    console.print("\n2. Deploy and run training DAG:")
    console.print("   [cyan]uv run python scripts/deploy_training_dag.py --run-dag[/cyan]")
    console.print("\n3. Deploy inference DAG (optional):")
    console.print("   [cyan]uv run python scripts/deploy_inference_dag.py --run-dag[/cyan]")
    console.print("\n4. Start inference workflow:")
    console.print("   [cyan]make -C ../../mock_data add-morning-data[/cyan]")
    console.print("   [cyan]make run-inference-dag[/cyan]")


def main():
    """Main entry point for deployment script."""
    parser = argparse.ArgumentParser(description="Deploy complete branch schema with all tables and stages")
    parser.add_argument("--dry-run", action="store_true", help="Validate configuration without making changes")
    args = parser.parse_args()

    try:
        deploy_schema(dry_run=args.dry_run)
    except Exception as e:
        console.print(f"\n[red]❌ Deployment failed: {e}[/red]")
        import sys

        sys.exit(1)


if __name__ == "__main__":
    main()
