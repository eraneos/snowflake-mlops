"""DAG packaging helpers for the PUDO project.

Builds the ``pudo.zip`` archive that Snowflake DAG tasks reference via
``imports=[...]`` and uploads it to the project stage. Also resolves the
exact runtime package set from ``projects/pudo/uv.lock`` (per ADR-0011 each
component owns its own lock).
"""

import logging
from pathlib import Path
import tempfile
import zipfile

from snowflake.snowpark import Session

logger = logging.getLogger(__name__)

# Python 3.11+ has tomllib built-in, Python 3.10 uses tomli
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


def package_and_upload_module(session: Session, stage: str) -> str:
    """Package and upload the pudo module to a stage as ``pudo.zip``.

    Returns:
        Stage path of the uploaded zip (e.g. ``@DB.SCHEMA.STAGE/packages/pudo.zip``).
    """
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_file:
        with zipfile.ZipFile(tmp_file.name, "w", zipfile.ZIP_DEFLATED) as zip_file:
            module_path = Path(__file__).parent.parent.parent
            pudo_path = module_path / "pudo"

            if pudo_path.exists():
                for py_file in pudo_path.rglob("*.py"):
                    archive_path = py_file.relative_to(module_path)
                    zip_file.write(py_file, archive_path)
                    logger.info(f"Added {archive_path} to package")
            else:
                logger.warning(f"pudo module not found at {pudo_path}")

        stage_path = f"{stage}/packages/pudo.zip"
        tmp_path = Path(tmp_file.name)
        with tmp_path.open("rb") as f:
            session.file.put_stream(f, stage_path, auto_compress=False, overwrite=True)

        logger.warning(f"Uploaded pudo module to {stage_path}")

    return f"{stage}/packages/pudo.zip"


def upload_module_as_directory(session: Session, stage: str) -> str:
    """Upload the pudo module as a directory tree (preserves structure).

    Required for ``submit_from_stage()`` so entrypoint scripts inside the package
    can be referenced by relative path.

    Returns:
        Stage directory path that received the uploaded files.
    """
    module_path = Path(__file__).parent.parent.parent
    pudo_path = module_path / "pudo"

    if not pudo_path.exists():
        logger.warning(f"pudo module not found at {pudo_path}")
        return f"{stage}/packages/"

    uploaded_count = 0
    for py_file in pudo_path.rglob("*.py"):
        relative_path = py_file.relative_to(module_path)
        stage_path = f"{stage}/packages/{relative_path.as_posix()}"

        try:
            with py_file.open("rb") as f:
                session.file.put_stream(
                    f,
                    stage_path,
                    auto_compress=False,
                    overwrite=True,
                )
            uploaded_count += 1
            logger.debug(f"Uploaded {relative_path} to {stage_path}")
        except Exception as e:
            logger.error(f"Failed to upload {relative_path} to {stage_path}: {e}")
            raise

    logger.info(f"Uploaded {uploaded_count} Python files from pudo module to {stage}/packages/")

    return f"{stage}/packages/"


def get_packages_from_pyproject() -> list[str]:
    """Extract pinned package versions from ``projects/pudo/uv.lock`` for DAG execution.

    Walks parent directories from this file's location until ``uv.lock`` is found.
    Per ADR-0011 each component owns its lock, so the walk lands at
    ``projects/pudo/uv.lock``. Returns ``"name==version"`` specs that Snowflake DAG
    tasks accept directly.

    Raises:
        RuntimeError: If ``tomllib``/``tomli`` is unavailable, ``uv.lock`` cannot be
            found, or no required packages are present in the lockfile.
    """
    if tomllib is None:
        msg = "tomllib/tomli not available - required for parsing uv.lock"
        raise RuntimeError(msg)

    current_file = Path(__file__).resolve()
    project_root = None
    for parent in [current_file, *list(current_file.parents)]:
        lock_path = parent / "uv.lock"
        if lock_path.exists():
            project_root = parent
            break

    if project_root is None:
        msg = "Could not find uv.lock file in project directory tree"
        raise RuntimeError(msg)

    lock_path = project_root / "uv.lock"
    with lock_path.open("rb") as f:
        lockfile = tomllib.load(f)

    packages = lockfile.get("package", [])

    needed_packages = {
        "snowflake-snowpark-python",
        "snowflake-ml-python",
        "xgboost",
        "pydantic",
        "pydantic-settings",
    }

    dag_packages = []
    for pkg in packages:
        pkg_name = pkg.get("name", "")
        pkg_version = pkg.get("version", "")

        if pkg_name in needed_packages:
            dag_packages.append(f"{pkg_name}=={pkg_version}")

    if not dag_packages:
        msg = f"No required packages found in uv.lock. Expected: {needed_packages}"
        raise RuntimeError(msg)

    logger.info(f"Loaded {len(dag_packages)} packages from uv.lock: {dag_packages}")
    return dag_packages
