"""Command-line interface for PUDO data generation."""

from pathlib import Path

import polars as pl
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import typer

from .config_models import get_generation_config
from .generators.delivery_attempts import DeliveryAttemptsGenerator
from .generators.occupancy import OccupancyGenerator
from .generators.parcels import ParcelsGenerator
from .generators.pudo import PudoGenerator

console = Console()
app = typer.Typer(help="PUDO Workshop Data Generator")


def _format_date_value(value) -> str:
    """Format a date value for display, handling None."""
    if value is None:
        return "None"
    return str(value)


def display_dataframe_summary(name: str, df: pl.DataFrame, *, show_sample: bool = True, n_rows: int = 5):
    """Display a comprehensive summary of a Polars DataFrame.

    Shows key information about the DataFrame including dimensions, column
    information, null counts, and a sample of the data (if requested).

    Args:
        name: Display name for the dataset (e.g., "PUDO_REFERENCE").
        df: Polars DataFrame to summarize.
        show_sample: Whether to show sample rows of data.
        n_rows: Number of sample rows to display (if show_sample is True).

    Example:
        >>> df = pl.DataFrame({"A": [1, 2, 3], "B": ["x", "y", "z"]})
        >>> display_dataframe_summary("TEST_DATA", df)
        📊 TEST_DATA
        Shape: 3 rows x 2 columns
        ...
    """
    console.print(f"\n[bold blue]📊 {name}[/bold blue]")
    console.print(f"Shape: {df.shape[0]:,} rows x {df.shape[1]} columns")

    # Column info
    console.print("\n[bold]Columns:[/bold]")
    for col in df.columns:
        dtype = str(df[col].dtype)
        null_count = df[col].null_count()
        console.print(f"  • {col}: {dtype} ({null_count:,} nulls)")

    if show_sample and len(df) > 0:
        console.print(f"\n[bold]Sample ({min(n_rows, len(df))} rows):[/bold]")

        # Create rich table
        table = Table(show_header=True, header_style="bold magenta")

        # Add columns
        for col in df.columns:
            table.add_column(col, style="cyan", no_wrap=False)

        # Add rows
        sample_df = df.head(n_rows)
        for row in sample_df.iter_rows():
            table.add_row(*[str(val) for val in row])

        console.print(table)


def display_data_quality_report(datasets: dict):
    """Display comprehensive data quality report for generated datasets.

    Analyzes each dataset and provides detailed statistics including row counts,
    null value analysis, and dataset-specific quality metrics such as:
    - PUDO type distributions and capacity statistics
    - Parcel size and weight distributions
    - Delivery attempt success rates and outcomes
    - Occupancy fill rates and utilization patterns

    Args:
        datasets: Dictionary mapping dataset names to Polars DataFrames.
                 Expected keys: "PUDO_REFERENCE", "PARCELS", "DELIVERY_ATTEMPTS", "PUDO_OCCUPANCY"

    Example:
        >>> datasets = {
        ...     "PUDO_REFERENCE": pudo_df,
        ...     "PARCELS": parcels_df,
        ...     "DELIVERY_ATTEMPTS": attempts_df,
        ...     "PUDO_OCCUPANCY": occupancy_df,
        ... }
        >>> display_data_quality_report(datasets)
    """
    console.print("\n[bold green]📋 Data Quality Report[/bold green]")

    # Overall stats
    total_rows = sum(len(df) for df in datasets.values())
    console.print(f"Total records generated: {total_rows:,}")

    # Per dataset stats
    for name, df in datasets.items():
        console.print(f"\n[bold]{name}:[/bold]")

        # Basic stats
        console.print(f"  Rows: {len(df):,}")
        console.print(f"  Columns: {len(df.columns)}")

        # Null counts
        null_counts = {col: df[col].null_count() for col in df.columns}
        if any(null_counts.values()):
            console.print("  Null values:")
            for col, nulls in null_counts.items():
                if nulls > 0:
                    console.print(f"    {col}: {nulls:,}")
        else:
            console.print("  ✅ No null values")

        # Specific checks per dataset
        if name == "PUDO_REFERENCE":
            unique_ids = df["PUDO_ID"].n_unique()
            console.print(f"  Unique PUDO IDs: {unique_ids}")
            pudo_types = df["PUDO_TYPE"].value_counts()
            console.print("  PUDO Types:")
            for row in pudo_types.iter_rows():
                ptype, count = row
                console.print(f"    {ptype}: {count}")

            # Capacity stats
            if "CAPACITY" in df.columns:
                avg_capacity = df["CAPACITY"].mean()
                min_capacity = df["CAPACITY"].min()
                max_capacity = df["CAPACITY"].max()
                console.print(f"  Capacity range: {min_capacity} - {max_capacity} (avg: {avg_capacity:.0f})")

        elif name == "PARCELS":
            unique_parcels = df["TRACKING_NUMBER"].n_unique()
            console.print(f"  Unique parcels: {unique_parcels:,}")
            if len(df) > 0:
                min_date = df["CREATED_DATE"].min()
                max_date = df["CREATED_DATE"].max()
                console.print(f"  Date range: {min_date} to {max_date}")

                # Parcel size distribution
                if "PARCEL_SIZE" in df.columns:
                    size_dist = df["PARCEL_SIZE"].value_counts()
                    console.print("  Parcel sizes:")
                    for row in size_dist.iter_rows():
                        size, count = row
                        pct = count / len(df) * 100
                        console.print(f"    {size}: {count} ({pct:.1f}%)")

                # Weight stats
                if "WEIGHT_KG" in df.columns:
                    avg_weight = df["WEIGHT_KG"].mean()
                    min_weight = df["WEIGHT_KG"].min()
                    max_weight = df["WEIGHT_KG"].max()
                    console.print(f"  Weight range: {min_weight:.1f} - {max_weight:.1f} kg (avg: {avg_weight:.1f} kg)")

        elif name == "DELIVERY_ATTEMPTS":
            unique_parcels = df["TRACKING_NUMBER"].n_unique()
            console.print(f"  Delivery attempts: {len(df):,}")
            console.print(f"  Unique parcels: {unique_parcels:,}")
            console.print(f"  Avg attempts per parcel: {len(df) / unique_parcels:.1f}")

            if len(df) > 0:
                min_date = df["ATTEMPT_DATE"].min()
                max_date = df["ATTEMPT_DATE"].max()
                console.print(f"  Date range: {min_date} to {max_date}")

                # Delivery status distribution
                status_dist = df["DELIVERY_STATUS"].value_counts()
                console.print("  Attempt outcomes:")
                for row in status_dist.iter_rows():
                    status, count = row
                    pct = count / len(df) * 100
                    console.print(f"    {status}: {count} ({pct:.1f}%)")

                # Check for capacity failures
                failed_deliveries = df.filter(pl.col("DELIVERY_STATUS") == "FAILED_NO_CAPACITY")
                if len(failed_deliveries) > 0:
                    console.print(f"  ⚠️  Failed deliveries due to no PUDO capacity: {len(failed_deliveries)}")

                # Attempt number distribution
                attempt_dist = df["ATTEMPT_NUMBER"].value_counts().sort("ATTEMPT_NUMBER")
                console.print("  Attempts distribution:")
                for row in attempt_dist.iter_rows():
                    attempt_num, count = row
                    console.print(f"    Attempt {attempt_num}: {count} deliveries")

                # Final outcomes per parcel
                final_outcomes = (
                    df.group_by("TRACKING_NUMBER")
                    .agg(pl.col("DELIVERY_STATUS").last().alias("FINAL_STATUS"))
                    .group_by("FINAL_STATUS")
                    .count()
                )
                console.print("  Final parcel outcomes:")
                for row in final_outcomes.iter_rows():
                    status, count = row
                    pct = count / unique_parcels * 100
                    console.print(f"    {status}: {count} ({pct:.1f}%)")

                # PUDO assignment analysis
                pudo_deliveries = df.filter(pl.col("PUDO_ID").is_not_null())
                if len(pudo_deliveries) > 0:
                    console.print(f"  PUDO redirections: {len(pudo_deliveries)} attempts")

                    # PUDO distribution
                    pudo_dist = pudo_deliveries["PUDO_ID"].value_counts().sort("PUDO_ID")
                    console.print("  PUDO assignment distribution:")
                    for row in pudo_dist.head(5).iter_rows():  # Show top 5
                        pudo_id, count = row
                        console.print(f"    PUDO {pudo_id}: {count} deliveries")

        elif name == "PUDO_OCCUPANCY":
            if len(df) > 0:
                avg_fill_rate = df["FILL_RATE"].mean()
                max_fill_rate = df["FILL_RATE"].max()
                min_fill_rate = df["FILL_RATE"].min()
                console.print(
                    f"  Fill rate range: {min_fill_rate:.1%} - {max_fill_rate:.1%} (avg: {avg_fill_rate:.1%})"
                )

                # Daily deliveries stats
                if "DAILY_DELIVERIES" in df.columns:
                    avg_daily = df["DAILY_DELIVERIES"].mean()
                    max_daily = df["DAILY_DELIVERIES"].max()
                    console.print(f"  Daily PUDO deliveries: avg {avg_daily:.0f}, max {max_daily}")


@app.command()
def inspect(
    output_dir: str = typer.Option(default="./data_output", help="Output directory for CSV files"),
    *,
    save_csv: bool = typer.Option(default=False, help="Save data to CSV files"),
    sample: bool = typer.Option(default=True, help="Show sample data"),
    sample_rows: int = typer.Option(default=5, help="Number of sample rows to show"),
    test_mode: bool = typer.Option(default=False, help="Generate small test dataset"),
) -> None:
    """Generate and inspect synthetic PUDO data without uploading to Snowflake.

    This command generates all four PUDO datasets (PUDO locations, parcels,
    delivery attempts, and occupancy data) and displays comprehensive summaries
    and quality reports. Optionally saves the data to CSV files.

    The command generates data sequentially in the correct dependency order:
    1. PUDO reference locations
    2. Parcels with destinations and characteristics
    3. Delivery attempts with success/failure outcomes
    4. PUDO occupancy and utilization statistics

    Args:
        save_csv: If True, save all datasets to CSV files in output_dir.
        output_dir: Directory path for CSV export (created if doesn't exist).
        sample: Whether to display sample rows for each dataset.
        sample_rows: Number of sample rows to show (1-100).
        test_mode: If True, generate smaller test datasets for quick validation.

    Example:
        >>> # Basic inspection with samples
        >>> pudo-generate inspect
        >>>
        >>> # Save to CSV files
        >>> pudo-generate inspect --save-csv --output-dir ./my_data
        >>>
        >>> # Test mode for quick validation
        >>> pudo-generate inspect --test-mode
    """

    console.print(Panel.fit("[bold blue]🔍 PUDO Data Inspector[/bold blue]", border_style="blue"))

    try:
        # Load configuration
        gen_config = get_generation_config()

        # Override for test mode
        if test_mode:
            gen_config.n_pudos = 10
            gen_config.n_days = 7
            gen_config.avg_parcels_per_day = 500
            console.print("🧪 [bold yellow]Test mode - generating small dataset[/bold yellow]")

        console.print(f"📊 Generating data: {gen_config.n_pudos} PUDOs, {gen_config.n_days} days")

        # Generate data in correct order
        with console.status("[bold green]Generating PUDO reference data..."):
            pudo_gen = PudoGenerator(gen_config)
            pudo_df = pudo_gen.generate()

        with console.status("[bold green]Generating parcels data..."):
            parcels_gen = ParcelsGenerator(gen_config)
            parcels_df = parcels_gen.generate()

        with console.status("[bold green]Generating delivery attempts data..."):
            attempts_gen = DeliveryAttemptsGenerator(gen_config, pudo_df, parcels_df)
            attempts_df = attempts_gen.generate()

        with console.status("[bold green]Generating occupancy data..."):
            occupancy_gen = OccupancyGenerator(gen_config, pudo_df, attempts_df)
            occupancy_df = occupancy_gen.generate()

        datasets = {
            "PUDO_REFERENCE": pudo_df,
            "PARCELS": parcels_df,
            "DELIVERY_ATTEMPTS": attempts_df,
            "PUDO_OCCUPANCY": occupancy_df,
        }

        # Display summaries
        for name, df in datasets.items():
            display_dataframe_summary(name=name, df=df, show_sample=sample, n_rows=sample_rows)

        # Display quality report
        display_data_quality_report(datasets)

        # Save to CSV if requested
        if save_csv:
            output_path = Path(output_dir)
            output_path.mkdir(exist_ok=True)

            console.print(f"\n[bold]💾 Saving to CSV files in {output_path}[/bold]")
            for name, df in datasets.items():
                csv_path = output_path / f"{name.lower()}.csv"
                df.write_csv(csv_path)
                console.print(f"  ✓ {csv_path}")

            console.print(f"\n✅ [bold green]Data saved to {output_path}[/bold green]")

        console.print("\n✅ [bold green]Data inspection complete![/bold green]")
        console.print("💡 Use --save-csv to export data to CSV files")
        console.print("💡 Use 'pudo-generate generate --upload' to push to Snowflake")

    except (ValueError, TypeError) as err:
        console.print(f"\n❌ [bold red]Data generation error: {err}[/bold red]")
        raise typer.Exit(1) from err
    except (FileNotFoundError, PermissionError) as err:
        console.print(f"\n❌ [bold red]File system error: {err}[/bold red]")
        raise typer.Exit(1) from err
    except (ImportError, ModuleNotFoundError) as err:
        console.print(f"\n❌ [bold red]Import error: {err}[/bold red]")
        raise typer.Exit(1) from err


@app.command("test-connection")
def test_connection() -> None:
    """Test Snowflake database connection and credentials.

    Establishes a connection to Snowflake using the configured credentials
    and tests basic connectivity by retrieving the Snowflake version.
    This command helps validate that all connection parameters are correct
    before attempting data upload operations.

    The command will display the Snowflake version if successful, or show
    detailed error information if the connection fails.

    Example:
        >>> # Test connection with current configuration
        >>> pudo-generate test-connection
        >>> # Expected output: "✅ Connection test passed! Snowflake version: X.X.X"
    """
    console.print(Panel.fit("[bold blue]Testing Snowflake Connection[/bold blue]", border_style="blue"))

    try:
        from pudo_data.core.session import create_session
        from pudo_data.core.sql_utils import test_connection as sql_test_connection

        session = create_session()
        version = sql_test_connection(session)
        console.print(f"\n✅ [bold green]Connection test passed! Snowflake version: {version}[/bold green]")

    except (ConnectionError, TimeoutError) as err:
        console.print(f"\n❌ [bold red]Connection error: {err}[/bold red]")
        raise typer.Exit(1) from err
    except (ImportError, ModuleNotFoundError) as err:
        console.print(f"\n❌ [bold red]Import error: {err}[/bold red]")
        raise typer.Exit(1) from err
    except (ValueError, TypeError) as err:
        console.print(f"\n❌ [bold red]Configuration error: {err}[/bold red]")
        raise typer.Exit(1) from err


@app.command("drop-database")
def drop_database(
    *,
    confirm: bool = typer.Option(default=False, help="Skip confirmation prompt"),
) -> None:
    """Drop the entire database from Snowflake.

    This command will permanently delete the entire database including all
    schemas, tables, and data. This is more destructive than drop-tables
    as it removes the entire database structure.

    Args:
        confirm: If True, skip the confirmation prompt and proceed directly.

    Example:
        >>> # Drop database with confirmation
        >>> pudo-generate drop-database
        >>>
        >>> # Drop database without confirmation prompt
        >>> pudo-generate drop-database --confirm
    """
    console.print(Panel.fit("[bold red]Drop Database from Snowflake[/bold red]", border_style="red"))

    if not confirm:
        confirm_drop = typer.confirm(
            "⚠️  This will permanently delete the ENTIRE DATABASE and all its contents. Are you sure?"
        )
        if not confirm_drop:
            console.print("❌ Operation cancelled")
            return

    try:
        from pudo_data.core.config import infra_config
        from pudo_data.core.session import create_session

        session = create_session()
        database = infra_config.database.name

        console.print(f"Dropping database {database}...")
        session.sql(f"DROP DATABASE IF EXISTS {database} CASCADE").collect()
        console.print("✅ [bold green]Database dropped successfully![/bold green]")

    except (ConnectionError, TimeoutError) as err:
        console.print(f"\n❌ [bold red]Connection error: {err}[/bold red]")
        raise typer.Exit(1) from err
    except (ValueError, TypeError) as err:
        console.print(f"\n❌ [bold red]Configuration error: {err}[/bold red]")
        raise typer.Exit(1) from err
    except (ImportError, ModuleNotFoundError) as err:
        console.print(f"\n❌ [bold red]Import error: {err}[/bold red]")
        raise typer.Exit(1) from err


@app.command("drop-tables")
def drop_tables(
    *,
    confirm: bool = typer.Option(default=False, help="Skip confirmation prompt"),
) -> None:
    """Drop all tables from Snowflake."""
    console.print(Panel.fit("[bold red]Drop Tables from Snowflake[/bold red]", border_style="red"))

    if not confirm:
        confirm_drop = typer.confirm("⚠️  This will permanently delete all PUDO workshop tables. Are you sure?")
        if not confirm_drop:
            console.print("❌ Operation cancelled")
            return

    try:
        from pudo_data.core.config import infra_config
        from pudo_data.core.session import create_session

        session = create_session()
        database = infra_config.database.name
        schema = infra_config.shared_data.schema_name  # mock_data only writes to SHARED_DATA per ADR-0005

        # Drop tables in reverse order due to foreign key constraints
        tables = ["PUDO_OCCUPANCY", "DELIVERY_ATTEMPTS", "PARCELS", "PUDO_REFERENCE"]
        for table_name in tables:
            console.print(f"Dropping {table_name}...")
            session.sql(f"DROP TABLE IF EXISTS {database}.{schema}.{table_name}").collect()

        console.print("✅ [bold green]All tables dropped successfully![/bold green]")

    except (ConnectionError, TimeoutError) as err:
        console.print(f"\n❌ [bold red]Connection error: {err}[/bold red]")
        raise typer.Exit(1) from err
    except (ValueError, TypeError) as err:
        console.print(f"\n❌ [bold red]Configuration error: {err}[/bold red]")
        raise typer.Exit(1) from err
    except (ImportError, ModuleNotFoundError) as err:
        console.print(f"\n❌ [bold red]Import error: {err}[/bold red]")
        raise typer.Exit(1) from err


@app.command("reset-data")
def reset_data(
    *,
    confirm: bool = typer.Option(default=False, help="Skip confirmation prompt"),
) -> None:
    """Drop and recreate all tables (fresh start)."""
    console.print(Panel.fit("[bold red]Reset All Data[/bold red]", border_style="red"))

    if not confirm:
        confirm_reset = typer.confirm(
            "⚠️  This will permanently delete all data and recreate empty tables. Are you sure?"
        )
        if not confirm_reset:
            console.print("❌ Operation cancelled")
            return

    try:
        from pudo_data.core.config import infra_config
        from pudo_data.core.session import create_session
        from pudo_data.core.sql_utils import execute_sql_file

        session = create_session()
        database = infra_config.database.name
        schema = infra_config.shared_data.schema_name  # mock_data only writes to SHARED_DATA per ADR-0005

        console.print("🗑️  Dropping existing tables...")
        # Drop tables in reverse order
        tables = ["PUDO_OCCUPANCY", "DELIVERY_ATTEMPTS", "PARCELS", "PUDO_REFERENCE"]
        for table_name in tables:
            session.sql(f"DROP TABLE IF EXISTS {database}.{schema}.{table_name}").collect()

        console.print("🏗️  Ensuring schema exists...")
        session.sql(f"CREATE SCHEMA IF NOT EXISTS {database}.{schema}").collect()
        session.sql(f"USE SCHEMA {database}.{schema}").collect()

        console.print("🏗️  Creating fresh tables from SQL templates...")
        execute_sql_file(session, "scripts/sql/tables/pudo_tables.sql", database=database, schema=schema)

        console.print("✅ [bold green]Data reset complete - fresh tables created![/bold green]")
        console.print("\n💡 Next step: Deploy schema and infrastructure:")
        console.print("   [cyan]make -C projects/pudo deploy-schema[/cyan]")

    except (ConnectionError, TimeoutError) as err:
        console.print(f"\n❌ [bold red]Connection error: {err}[/bold red]")
        raise typer.Exit(1) from err
    except (ValueError, TypeError) as err:
        console.print(f"\n❌ [bold red]Configuration error: {err}[/bold red]")
        raise typer.Exit(1) from err
    except (ImportError, ModuleNotFoundError) as err:
        console.print(f"\n❌ [bold red]Import error: {err}[/bold red]")
        raise typer.Exit(1) from err


@app.command()
def generate(
    *,
    upload: bool = typer.Option(default=True, help="Upload to Snowflake"),
    validate: bool = typer.Option(default=True, help="Validate data"),
    test_mode: bool = typer.Option(default=False, help="Generate small test dataset"),
) -> None:
    """Generate synthetic PUDO data and optionally upload to Snowflake.

    This is the main data generation command that creates all PUDO datasets
    and can upload them directly to Snowflake. The command generates data
    in the correct dependency order and handles the complete workflow from
    generation to validation.

    The generation process includes:
    1. Generate PUDO reference locations with realistic Berlin geography
    2. Create parcel data with various sizes, weights, and destinations
    3. Simulate delivery attempts with configurable success rates
    4. Calculate PUDO occupancy and utilization statistics
    5. Upload to Snowflake (if requested) with validation

    Args:
        upload: Whether to upload generated data to Snowflake database.
        validate: Whether to validate uploaded data by checking row counts.
        test_mode: Generate smaller datasets for quick testing and validation.

    Example:
        >>> # Generate and upload to Snowflake with validation
        >>> pudo-generate generate
        >>>
        >>> # Generate locally without uploading
        >>> pudo-generate generate --no-upload
        >>>
        >>> # Quick test generation
        >>> pudo-generate generate --test-mode
    """

    console.print(
        Panel.fit("[bold blue]Berlin PUDO Capacity Prediction Data Generator[/bold blue]", border_style="blue")
    )

    try:
        # Load configuration
        gen_config = get_generation_config()

        # Override for test mode
        if test_mode:
            gen_config.n_pudos = 10
            gen_config.n_days = 7
            gen_config.avg_parcels_per_day = 500
            console.print("🧪 [bold yellow]Test mode - generating small dataset[/bold yellow]")

        console.print(f"📊 Generating data: {gen_config.n_pudos} PUDOs, {gen_config.n_days} days")

        # Generate data in correct order
        with console.status("[bold green]Generating PUDO reference data..."):
            pudo_gen = PudoGenerator(gen_config)
            pudo_df = pudo_gen.generate()

        with console.status("[bold green]Generating parcels data..."):
            parcels_gen = ParcelsGenerator(gen_config)
            parcels_df = parcels_gen.generate()

        with console.status("[bold green]Generating delivery attempts data..."):
            attempts_gen = DeliveryAttemptsGenerator(gen_config, pudo_df, parcels_df)
            attempts_df = attempts_gen.generate()

        with console.status("[bold green]Generating occupancy data..."):
            occupancy_gen = OccupancyGenerator(gen_config, pudo_df, attempts_df)
            occupancy_df = occupancy_gen.generate()

        datasets = {
            "PUDO_REFERENCE": pudo_df,
            "PARCELS": parcels_df,
            "DELIVERY_ATTEMPTS": attempts_df,
            "PUDO_OCCUPANCY": occupancy_df,
        }

        # Print summary
        console.print("\n[bold]Dataset Summary:[/bold]")
        for name, df in datasets.items():
            console.print(f"  {name}: {len(df):,} rows")

        if upload:
            # Upload to Snowflake
            from pudo_data.core.config import infra_config
            from pudo_data.core.session import create_session
            from pudo_data.core.sql_utils import test_connection as sql_test_connection

            session = create_session(schema=infra_config.shared_data.schema_name)

            # Test connection first
            version = sql_test_connection(session)
            console.print(f"✅ Connected to Snowflake version: {version}")

            # Upload data (tables should already exist from deployment)
            console.print("\n📤 Uploading data to Snowflake...")
            upload_order = ["PUDO_REFERENCE", "PARCELS", "DELIVERY_ATTEMPTS", "PUDO_OCCUPANCY"]

            for table_name in upload_order:
                if table_name in datasets:
                    df = datasets[table_name]
                    console.print(f"  Uploading {len(df):,} rows to {table_name}...")

                    # Convert to Snowpark DataFrame
                    pandas_df = df.to_pandas()
                    snowpark_df = session.create_dataframe(pandas_df)

                    # Use temp table + INSERT to preserve existing table schema
                    # (avoids save_as_table() overwriting DATE types with VARCHAR)
                    from datetime import datetime

                    temp_table = f"TEMP_{table_name}_{int(datetime.now().timestamp())}"
                    snowpark_df.write.mode("overwrite").save_as_table(temp_table)

                    # Get DataFrame columns for explicit INSERT
                    columns = snowpark_df.columns
                    columns_str = ", ".join(columns)

                    # Clear existing data and insert from temp table
                    session.sql(f"TRUNCATE TABLE IF EXISTS {table_name}").collect()
                    insert_sql = f"""
                        INSERT INTO {table_name} ({columns_str})
                        SELECT {columns_str} FROM {temp_table}
                    """
                    session.sql(insert_sql).collect()

                    # Drop temp table
                    session.sql(f"DROP TABLE IF EXISTS {temp_table}").collect()

            console.print("✅ Upload complete")

            if validate:
                # Basic validation - check row counts
                console.print("\n🔍 Validating uploaded data...")
                for table_name in datasets:
                    result = session.sql(f"SELECT COUNT(*) FROM {table_name}").collect()
                    count = result[0][0]
                    expected = len(datasets[table_name])
                    if count == expected:
                        console.print(f"  ✅ {table_name}: {count:,} rows (matches expected)")
                    else:
                        console.print(f"  ❌ {table_name}: {count:,} rows (expected {expected:,})")

            console.print("\n✅ [bold green]Data generation and upload complete![/bold green]")
            console.print("\n💡 Note: If tables don't exist, run schema deployment first:")
            console.print("   [cyan]make -C projects/pudo deploy-schema[/cyan]")
        else:
            console.print("\n✅ [bold green]Data generation complete![/bold green]")
            console.print("💡 Use --upload to push data to Snowflake")

    except (ValueError, TypeError) as err:
        console.print(f"\n❌ [bold red]Data generation error: {err}[/bold red]")
        raise typer.Exit(1) from err
    except (ConnectionError, TimeoutError) as err:
        console.print(f"\n❌ [bold red]Connection error: {err}[/bold red]")
        raise typer.Exit(1) from err
    except (FileNotFoundError, PermissionError) as err:
        console.print(f"\n❌ [bold red]File system error: {err}[/bold red]")
        raise typer.Exit(1) from err
    except (ImportError, ModuleNotFoundError) as err:
        console.print(f"\n❌ [bold red]Import error: {err}[/bold red]")
        raise typer.Exit(1) from err


@app.command("add-day")
def add_day(
    phase: str = typer.Argument(..., help="Phase to run: 'morning' or 'evening'"),
    target_date: str = typer.Option(None, help="Specific date (YYYY-MM-DD), default: auto-detect"),
) -> None:
    """Generate incremental data for a new simulation day.

    This command supports the workshop inference workflow by generating data
    in two phases:

    Morning Phase: Generates parcels and delivery attempts (data known in the morning)
    Evening Phase: Generates ground truth occupancy (known at end of day)

    Example:
        >>> # Generate morning data for next day
        >>> pudo-generate add-day morning
        >>>
        >>> # Generate evening data for specific date
        >>> pudo-generate add-day evening --target-date 2024-01-15
    """
    from datetime import datetime

    console.print(Panel.fit(f"[bold blue]Generate {phase.title()} Data[/bold blue]", border_style="blue"))

    if phase not in ["morning", "evening"]:
        console.print("❌ [bold red]Phase must be 'morning' or 'evening'[/bold red]")
        raise typer.Exit(1)

    try:
        from pudo_data.core.config import infra_config
        from pudo_data.core.session import create_session
        from pudo_data.incremental_generator import IncrementalDataGenerator

        session = create_session(schema=infra_config.shared_data.schema_name)
        gen_config = get_generation_config()
        generator = IncrementalDataGenerator(session, gen_config)

        # Parse target date if provided
        parsed_date = None
        if target_date:
            try:
                parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            except ValueError as err:
                console.print(f"❌ [bold red]Invalid date format: {err}[/bold red]")
                raise typer.Exit(1) from err

        # Generate data based on phase
        if phase == "morning":
            stats = generator.generate_morning_data(parsed_date)
            console.print(f"\n✅ [bold green]Morning data generated for {stats['simulation_date']}[/bold green]")
            console.print(f"  Parcels: {stats['parcels_count']:,}")
            console.print(f"  Delivery attempts: {stats['attempts_count']:,}")
            console.print("\n💡 Next steps:")
            console.print("  1. Run inference: pudo-inference run")
            console.print(
                f"  2. Generate evening data: pudo-generate add-day evening --target-date {stats['simulation_date']}"
            )

        else:  # evening
            stats = generator.generate_evening_data(parsed_date)
            console.print(f"\n✅ [bold green]Evening data generated for {stats['simulation_date']}[/bold green]")
            console.print(f"  Occupancy records: {stats['occupancy_count']:,}")
            console.print(f"  Predictions updated: {stats['predictions_updated']:,}")
            console.print("\n💡 Next step:")
            console.print("  Evaluate predictions: pudo-inference evaluate")

    except ValueError as err:
        console.print(f"\n❌ [bold red]Error: {err}[/bold red]")
        raise typer.Exit(1) from err
    except (ConnectionError, TimeoutError) as err:
        console.print(f"\n❌ [bold red]Connection error: {err}[/bold red]")
        raise typer.Exit(1) from err
    except (ImportError, ModuleNotFoundError) as err:
        console.print(f"\n❌ [bold red]Import error: {err}[/bold red]")
        raise typer.Exit(1) from err


@app.command("simulation-status")
def simulation_status() -> None:
    """Show current simulation status and statistics.

    Displays:
    - Next simulation date to generate
    - Total days generated
    - Last phase dates
    - Dates pending predictions

    Example:
        >>> pudo-generate simulation-status
    """
    console.print(Panel.fit("[bold blue]Simulation Status[/bold blue]", border_style="blue"))

    try:
        from pudo_data.core.config import infra_config
        from pudo_data.core.session import create_session
        from pudo_data.incremental_generator import IncrementalDataGenerator

        session = create_session(schema=infra_config.shared_data.schema_name)
        gen_config = get_generation_config()
        generator = IncrementalDataGenerator(session, gen_config)

        status = generator.get_simulation_status()

        # Display status table
        table = Table(title="Simulation Progress", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        table.add_row("Next Simulation Date", _format_date_value(status["next_simulation_date"]))
        table.add_row("Total Days Generated", str(status["total_days_generated"]))
        table.add_row("Last Morning Phase", _format_date_value(status["last_morning_date"]))
        table.add_row("Last Evening Phase", _format_date_value(status["last_evening_date"]))

        console.print(table)

        # Show pending predictions
        if status["pending_predictions"]:
            console.print(
                f"\n[bold yellow]⚠️  {len(status['pending_predictions'])} date(s) need predictions:[/bold yellow]"
            )
            for pending_date in status["pending_predictions"]:
                console.print(f"  • {pending_date}")
            console.print("\n💡 Run: pudo-inference run")
        else:
            console.print("\n✅ [bold green]All generated dates have predictions[/bold green]")

    except (ConnectionError, TimeoutError) as err:
        console.print(f"\n❌ [bold red]Connection error: {err}[/bold red]")
        raise typer.Exit(1) from err
    except (ImportError, ModuleNotFoundError) as err:
        console.print(f"\n❌ [bold red]Import error: {err}[/bold red]")
        raise typer.Exit(1) from err


@app.command("reset-simulation")
def reset_simulation(
    *,
    confirm: bool = typer.Option(default=False, help="Skip confirmation prompt"),
) -> None:
    """Reset simulation state and clear incremental data.

    This will:
    - Clear DATA_GENERATION_LOG table
    - Clear PREDICTIONS table
    - Keep PUDO_REFERENCE (base data)
    - Clear PARCELS, DELIVERY_ATTEMPTS, PUDO_OCCUPANCY

    Example:
        >>> pudo-generate reset-simulation --confirm
    """
    console.print(Panel.fit("[bold red]Reset Simulation[/bold red]", border_style="red"))

    if not confirm:
        confirm_reset = typer.confirm("⚠️  This will delete all incremental data and predictions. Continue?")
        if not confirm_reset:
            console.print("❌ Operation cancelled")
            return

    try:
        from pudo_data.core.config import infra_config
        from pudo_data.core.environment import detect_environment, get_project_schema
        from pudo_data.core.session import create_session

        session = create_session()
        database = infra_config.database.name
        schema = get_project_schema(detect_environment())  # `PUDO_<ENV>` per ADR-0004
        shared_data_schema = infra_config.shared_data.schema_name

        # Get all simulation dates from the generation log (these are incremental additions)
        console.print("Identifying incremental data to remove...")
        try:
            result = session.sql(  # Config values, not user input
                f"""
                SELECT DISTINCT SIMULATION_DATE
                FROM {database}.{shared_data_schema}.DATA_GENERATION_LOG
                ORDER BY SIMULATION_DATE
                """
            ).collect()
            simulation_dates = [row["SIMULATION_DATE"] for row in result]

            if simulation_dates:
                console.print(f"Found {len(simulation_dates)} simulation dates to remove")
            else:
                console.print("[yellow]No incremental simulation data found[/yellow]")
                console.print("\n✅ [bold green]Nothing to reset![/bold green]")
                return

        except Exception as e:
            console.print(f"[yellow]Could not read DATA_GENERATION_LOG: {e}[/yellow]")
            console.print("[yellow]Assuming no incremental data exists[/yellow]")
            return

        # Delete incremental data from shared data tables (only rows with dates in simulation log)
        tables_with_dates = {
            "PARCELS": "CREATED_DATE",
            "DELIVERY_ATTEMPTS": "ATTEMPT_DATE",
            "PUDO_OCCUPANCY": "DATE",
        }

        for table_name, date_column in tables_with_dates.items():
            try:
                console.print(f"Removing incremental {table_name} data...")
                # Build IN clause with dates
                dates_str = ", ".join([f"'{date}'" for date in simulation_dates])
                delete_sql = f"""
                    DELETE FROM {database}.{shared_data_schema}.{table_name}
                    WHERE {date_column} IN ({dates_str})
                """  # Table/column names from config, dates from Snowflake query
                result = session.sql(delete_sql).collect()
                console.print(f"  Removed rows from {table_name}")
            except Exception as e:
                console.print(f"[yellow]Could not clear {table_name}: {e}[/yellow]")

        # Clear branch-specific predictions table (all predictions are tied to incremental workflow)
        try:
            console.print("Clearing predictions...")
            session.sql(f"TRUNCATE TABLE IF EXISTS {database}.{schema}.PREDICTIONS").collect()
        except Exception as e:
            console.print(f"[yellow]Could not clear PREDICTIONS: {e}[/yellow]")

        # Clear the generation log (last step, after data is removed)
        try:
            console.print("Clearing simulation log...")
            session.sql(f"TRUNCATE TABLE IF EXISTS {database}.{shared_data_schema}.DATA_GENERATION_LOG").collect()
        except Exception as e:
            console.print(f"[yellow]Could not clear DATA_GENERATION_LOG: {e}[/yellow]")

        console.print("\n✅ [bold green]Simulation reset complete![/bold green]")
        console.print("💡 Initial dataset preserved, incremental simulation data removed")
        console.print("💡 Ready to start new simulation with: pudo-generate add-day morning")

    except (ConnectionError, TimeoutError) as err:
        console.print(f"\n❌ [bold red]Connection error: {err}[/bold red]")
        raise typer.Exit(1) from err


def main() -> None:
    """Main entry point for the PUDO data generation CLI.

    This function serves as the primary entry point when the module is
    executed directly. It delegates to the Typer CLI application which
    handles command routing and execution.

    Example:
        >>> # Run the CLI application
        >>> python -m pudo_data.cli
        >>>
        >>> # Or execute directly
        >>> python src/pudo_data/cli.py
    """
    app()


if __name__ == "__main__":
    main()
