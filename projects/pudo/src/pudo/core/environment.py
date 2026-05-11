"""Environment detection and per-env schema name helpers for the PUDO project.

Per ADR-0004, schemas are environment-keyed by a fixed pattern:
- Project schema: ``<PROJECT>_<ENV>``     (e.g. ``PUDO_DEV``)
- Feature store: ``FEATURE_STORE_<ENV>``  (e.g. ``FEATURE_STORE_DEV``)
- Model registry: ``MODEL_REGISTRY_<ENV>`` (e.g. ``MODEL_REGISTRY_DEV``)

Per ADR-0001 each component carries its own minimal ``core/``; this module is
duplicated from hub-side and is a candidate for centralization once ADR-0020 lands.
"""

from pathlib import Path
import re
import subprocess
from typing import Literal

from snowflake.core.task.context import TaskContext

Env = Literal["dev", "staging", "prod"]

PROJECT_NAME = "PUDO"

REPO_ROOT = Path(__file__).resolve().parents[5]


def detect_environment() -> Env:
    """Detect environment from local git state. Used outside Snowflake task graphs."""
    try:
        result = subprocess.run(
            ["git", "describe", "--exact-match", "--tags"],
            capture_output=True,
            text=True,
            check=False,
            cwd=REPO_ROOT,
        )
        if result.returncode == 0 and re.match(r"^v\d+\.\d+", result.stdout.strip()):
            return "prod"

        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
        branch = result.stdout.strip()
        if branch.startswith(("feat/", "bugfix/", "feature/", "fix/")):
            return "dev"
        if branch == "main":
            return "staging"
        return "dev"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "dev"


def get_environment_from_context(ctx: TaskContext) -> Env:
    """Resolve environment inside a Snowflake Tasks DAG run.

    Reads the ``environment`` key from the task graph config supplied at deploy time.
    Falls back to ``"dev"`` if the key is missing.
    """
    graph_config = ctx.get_task_graph_config() or {}
    env = graph_config.get("environment", "dev")
    if env not in ("dev", "staging", "prod"):
        msg = f"Invalid environment in task graph config: {env!r}"
        raise ValueError(msg)
    return env


def get_project_schema(env: Env) -> str:
    return f"{PROJECT_NAME}_{env.upper()}"


def get_feature_store_schema(env: Env) -> str:
    return f"FEATURE_STORE_{env.upper()}"


def get_registry_schema(env: Env) -> str:
    return f"MODEL_REGISTRY_{env.upper()}"
