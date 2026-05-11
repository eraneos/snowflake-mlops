"""Environment detection from git for mock_data operations.

Mock data is env-aware in two places:
- the `SHARED_DATA` schema is env-agnostic (only one copy, populated once)
- the project-side `PREDICTIONS` table that the incremental simulator writes
  back to is env-scoped (`PUDO_<ENV>` per ADR-0004)

Per ADR-0001 mock_data does not import from projects. Mock data is PUDO-domain
at baseline (per ADR-0005), so the project schema name is computed locally
using the same convention as `projects/pudo/src/pudo/core/environment.py`.
"""

from pathlib import Path
import re
import subprocess
from typing import Literal

Env = Literal["dev", "staging", "prod"]

REPO_ROOT = Path(__file__).resolve().parents[4]

PROJECT_NAME = "PUDO"


def detect_environment() -> Env:
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


def get_project_schema(env: Env) -> str:
    return f"{PROJECT_NAME}_{env.upper()}"
