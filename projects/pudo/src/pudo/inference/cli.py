"""Command-line interface for PUDO inference pipeline."""

from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import typer

console = Console()
app = typer.Typer(help="PUDO Inference Pipeline")


@app.command("run")
def run_inference_cmd(
    target_date: str = typer.Option(None, "--date", help="Date to predict (YYYY-MM-DD), default: auto-detect"),
) -> None:
    """Run inference on new data to predict PUDO fill rates.

    This command loads the latest promoted model and generates predictions
    for PUDOs on the specified date (or the latest date with morning data).

    Example:
        >>> # Run inference on latest date
        >>> pudo-inference run
        >>>
        >>> # Run inference on specific date
        >>> pudo-inference run --date 2024-01-15
    """
    console.print(Panel.fit("[bold blue]Run PUDO Capacity Inference[/bold blue]", border_style="blue"))

    try:
        from pudo.core.snowflake_session import create_session
        from pudo.inference.ops import run_inference

        session = create_session()

        # Parse target date if provided
        parsed_date = None
        if target_date:
            try:
                parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            except ValueError as err:
                console.print(f"❌ [bold red]Invalid date format: {err}[/bold red]")
                raise typer.Exit(1) from err

        # Run inference
        with console.status("[bold green]Loading model and generating predictions..."):
            stats = run_inference(session, parsed_date)

        console.print(f"\n✅ [bold green]Inference complete for {stats['prediction_date']}[/bold green]")
        console.print(f"  Model version: {stats['model_version']}")
        console.print(f"  PUDOs predicted: {stats['pudos_predicted']:,}")
        console.print(f"  High-risk PUDOs (>85%): {stats['high_risk_count']:,}")

        if stats["high_risk_count"] > 0:
            console.print(
                f"\n⚠️  [bold yellow]{stats['high_risk_count']} PUDOs predicted to exceed 85% capacity[/bold yellow]"
            )
            console.print("💡 View alerts: pudo-inference alerts")

        console.print("\n💡 Next step:")
        console.print(
            f"  Generate evening data: pudo-generate add-day evening --target-date {stats['prediction_date']}"
        )

    except ValueError as err:
        console.print(f"\n❌ [bold red]Error: {err}[/bold red]")
        raise typer.Exit(1) from err
    except (ConnectionError, TimeoutError) as err:
        console.print(f"\n❌ [bold red]Connection error: {err}[/bold red]")
        raise typer.Exit(1) from err
    except (ImportError, ModuleNotFoundError) as err:
        console.print(f"\n❌ [bold red]Import error: {err}[/bold red]")
        raise typer.Exit(1) from err


@app.command("evaluate")
def evaluate_cmd(
    target_date: str = typer.Option(None, "--date", help="Date to evaluate (YYYY-MM-DD), default: latest"),
) -> None:
    """Evaluate prediction accuracy against actual outcomes.

    This command compares predictions with actual fill rates (generated
    during evening phase) and calculates accuracy metrics.

    Example:
        >>> # Evaluate latest predictions
        >>> pudo-inference evaluate
        >>>
        >>> # Evaluate specific date
        >>> pudo-inference evaluate --date 2024-01-15
    """
    console.print(Panel.fit("[bold blue]Evaluate Predictions[/bold blue]", border_style="blue"))

    try:
        from pudo.core.snowflake_session import create_session
        from pudo.inference.ops import evaluate_predictions

        session = create_session()

        # Parse target date if provided
        parsed_date = None
        if target_date:
            try:
                parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            except ValueError as err:
                console.print(f"❌ [bold red]Invalid date format: {err}[/bold red]")
                raise typer.Exit(1) from err

        # Evaluate predictions
        evaluation = evaluate_predictions(session, parsed_date)

        console.print(f"\n✅ [bold green]Evaluation complete for {evaluation['prediction_date']}[/bold green]")

        # Display metrics table
        table = Table(title="Prediction Accuracy Metrics", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        table.add_row("Predictions Evaluated", f"{evaluation['predictions_evaluated']:,}")
        table.add_row("Mean Absolute Error (MAE)", f"{evaluation['mae']:.4f}")
        table.add_row("Root Mean Squared Error (RMSE)", f"{evaluation['rmse']:.4f}")
        table.add_row("Mean Error (Bias)", f"{evaluation['mean_error']:.4f}")

        if evaluation["total_alerts"] > 0:
            alert_accuracy = (evaluation["correct_alerts"] / evaluation["total_alerts"]) * 100
            table.add_row("Total High-Risk Alerts", f"{evaluation['total_alerts']}")
            table.add_row("Correct Alerts", f"{evaluation['correct_alerts']}")
            table.add_row("Alert Accuracy", f"{alert_accuracy:.1f}%")

        console.print(table)

        # Interpretation
        if evaluation["mae"] < 0.10:
            console.print("\n✅ [bold green]Excellent prediction accuracy![/bold green]")
        elif evaluation["mae"] < 0.20:
            console.print("\n👍 [bold yellow]Good prediction accuracy[/bold yellow]")
        else:
            console.print("\n⚠️  [bold yellow]Consider model retraining[/bold yellow]")

    except ValueError as err:
        console.print(f"\n❌ [bold red]Error: {err}[/bold red]")
        raise typer.Exit(1) from err
    except (ConnectionError, TimeoutError) as err:
        console.print(f"\n❌ [bold red]Connection error: {err}[/bold red]")
        raise typer.Exit(1) from err
    except (ImportError, ModuleNotFoundError) as err:
        console.print(f"\n❌ [bold red]Import error: {err}[/bold red]")
        raise typer.Exit(1) from err


@app.command("alerts")
def alerts_cmd(
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum number of alerts to show"),
) -> None:
    """Show current high-risk PUDO alerts (predicted fill rate > 85%).

    Example:
        >>> # Show top 20 alerts
        >>> pudo-inference alerts
        >>>
        >>> # Show top 10 alerts
        >>> pudo-inference alerts --limit 10
    """
    console.print(Panel.fit("[bold yellow]High-Risk PUDO Alerts[/bold yellow]", border_style="yellow"))

    try:
        from pudo.core.snowflake_session import get_session
        from pudo.inference.ops import get_current_alerts

        session = get_session()
        alerts_df = get_current_alerts(session)

        if len(alerts_df) == 0:
            console.print("\n✅ [bold green]No high-risk PUDOs currently[/bold green]")
            return

        console.print(f"\n⚠️  [bold yellow]{len(alerts_df)} high-risk PUDO(s) found[/bold yellow]")

        # Display alerts table
        table = Table(show_header=True, header_style="bold red")
        table.add_column("PUDO ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="white")
        table.add_column("Type", style="yellow")
        table.add_column("Date", style="white")
        table.add_column("Predicted Fill", style="red", justify="right")
        table.add_column("Capacity", style="white", justify="right")
        table.add_column("Est. Occupancy", style="red", justify="right")

        for row in alerts_df.head(limit).iter_rows(named=True):
            table.add_row(
                str(row["PUDO_ID"]),
                row["PUDO_NAME"],
                row["PUDO_TYPE"],
                str(row["PREDICTION_DATE"]),
                f"{row['PREDICTED_FILL_RATE']:.1%}",
                str(row["CAPACITY"]),
                str(row["PREDICTED_OCCUPANCY"]),
            )

        console.print(table)

        console.print("\n💡 Consider deploying mobile pods to high-risk locations")

    except (ConnectionError, TimeoutError) as err:
        console.print(f"\n❌ [bold red]Connection error: {err}[/bold red]")
        raise typer.Exit(1) from err
    except (ImportError, ModuleNotFoundError) as err:
        console.print(f"\n❌ [bold red]Import error: {err}[/bold red]")
        raise typer.Exit(1) from err


@app.command("summary")
def summary_cmd() -> None:
    """Show summary of all prediction metrics across dates.

    Example:
        >>> pudo-inference summary
    """
    console.print(Panel.fit("[bold blue]Inference Metrics Summary[/bold blue]", border_style="blue"))

    try:
        from pudo.core.config.infrastructure import config as infra_config
        from pudo.core.environment import detect_environment, get_project_schema
        from pudo.core.snowflake_session import create_session

        session = create_session()
        schema_name = get_project_schema(detect_environment())

        # Query metrics view
        result = session.sql(
            f"""
            SELECT *
            FROM {infra_config.database.name}.{schema_name}.INFERENCE_METRICS
            ORDER BY PREDICTION_DATE DESC
            LIMIT 10
        """
        ).collect()

        if not result:
            console.print("\n⚠️  [bold yellow]No evaluation data available yet[/bold yellow]")
            console.print("💡 Run evening data generation and evaluate predictions")
            return

        # Display metrics table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Date", style="cyan")
        table.add_column("Model Version", style="white")
        table.add_column("Predictions", style="green", justify="right")
        table.add_column("MAE", style="yellow", justify="right")
        table.add_column("RMSE", style="yellow", justify="right")

        for row in result:
            table.add_row(
                str(row["PREDICTION_DATE"]),
                row["MODEL_VERSION"],
                str(row["PREDICTIONS_WITH_ACTUALS"]),
                f"{float(row['MEAN_ABSOLUTE_ERROR']):.4f}" if row["MEAN_ABSOLUTE_ERROR"] else "N/A",
                f"{float(row['RMSE']):.4f}" if row["RMSE"] else "N/A",
            )

        console.print(table)

        # Overall statistics
        overall_result = session.sql(
            f"""
            SELECT
                COUNT(DISTINCT PREDICTION_DATE) as total_days,
                AVG(MEAN_ABSOLUTE_ERROR) as avg_mae,
                AVG(RMSE) as avg_rmse
            FROM {infra_config.database.name}.{schema_name}.INFERENCE_METRICS
        """
        ).collect()

        if overall_result:
            stats = overall_result[0]
            console.print("\n[bold]Overall Statistics:[/bold]")
            console.print(f"  Total days evaluated: {stats['TOTAL_DAYS']}")
            console.print(f"  Average MAE: {float(stats['AVG_MAE']):.4f}" if stats["AVG_MAE"] else "  Average MAE: N/A")
            console.print(
                f"  Average RMSE: {float(stats['AVG_RMSE']):.4f}" if stats["AVG_RMSE"] else "  Average RMSE: N/A"
            )

    except (ConnectionError, TimeoutError) as err:
        console.print(f"\n❌ [bold red]Connection error: {err}[/bold red]")
        raise typer.Exit(1) from err
    except (ImportError, ModuleNotFoundError) as err:
        console.print(f"\n❌ [bold red]Import error: {err}[/bold red]")
        raise typer.Exit(1) from err


def main() -> None:
    """Main entry point for the inference CLI."""
    app()


if __name__ == "__main__":
    main()
