"""Environment detection from git for hub deploy operations.

Hub itself is env-agnostic at the resource layer (one set of account-level
objects per ADR-0004). Env detection is used only for selecting which
per-env shared schemas to bootstrap when the user wants to scope a deploy.
The default bootstrap creates DEV, STAGING, and PROD shared schemas in one
pass, so env detection is informational by default.

Per ADR-0001 hub does not import from projects; per ADR-0003 each component
carries a minimal `core/`. This file is duplicated from project-side and is
a candidate for centralization once ADR-0020 lands.
"""

from pathlib import Path
import re
import subprocess
from typing import Literal

Env = Literal["dev", "staging", "prod"]

REPO_ROOT = Path(__file__).resolve().parents[4]


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
