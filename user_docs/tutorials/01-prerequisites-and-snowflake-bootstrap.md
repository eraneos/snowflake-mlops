# Tutorial 1: Prerequisites & Snowflake Bootstrap

This tutorial walks you through the one-time setup needed before you can deploy
any component of the reference repository.

## What you will learn

- Which tools must be installed locally.
- How to configure Snowflake connection credentials.
- How to bootstrap the shared platform infrastructure (hub).

## Prerequisites

### Local tooling

| Tool | Version | Installation |
|---|---|---|
| Python | 3.10 | Use `pyenv`, `uv`, or your system package manager. |
| [uv](https://docs.astral.sh/uv/) | Latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Git | Latest | System package manager. |

!!! warning "Python version"
    All components in this repository pin **Python 3.10** for Snowflake
    runtime compatibility. Do not use Python 3.11+.

### Snowflake access

You need a Snowflake account where you can temporarily assume the
`ACCOUNTADMIN` role for the initial hub bootstrap. After bootstrap, day-to-day
operations use purpose-built roles created by the hub.

## Step 1: Clone the repository

```bash
git clone <repository-url>
cd gls-snowflake-workshop
```

## Step 2: Configure environment variables

Each component reads its Snowflake connection settings from a `.env` file in
its own directory. At minimum, you need a `.env` file for the hub and for each
project you plan to run.

Create `hub/.env`:

```dotenv
SNOWFLAKE_ACCOUNT=<your-account-identifier>
SNOWFLAKE_USER=<your-username>
SNOWFLAKE_ROLE=ACCOUNTADMIN
SNOWFLAKE_WAREHOUSE=<warehouse-name>
```

Create `projects/pudo/.env` (you can symlink it to `hub/.env` if the
credentials are the same):

```bash
cd projects/pudo
ln -s ../../hub/.env .env
```

Repeat for `mock_data/.env` if you plan to seed data from a separate terminal
session.

!!! tip "Environment selection"
    The repository currently uses the **Git branch name** to determine which
    Snowflake environment (dev, staging, prod) to target. This means your
    `.env` should use a role and warehouse appropriate for the environment
    you are bootstrapping.

## Step 3: Bootstrap hub infrastructure

The hub component creates the shared Snowflake databases, schemas, warehouses,
roles, and compute pools that all projects depend on.

```bash
cd hub
make deploy-infra
```

This runs `uv run python scripts/deploy_infra.py`, which:

1. Creates the shared database and schemas.
2. Creates operational roles and grants.
3. Creates warehouses for training and inference workloads.
4. Creates compute pools for container-based training.

!!! note "ACCOUNTADMIN requirement"
    The initial bootstrap requires `ACCOUNTADMIN` because it creates
    account-level objects (databases, roles, warehouses). After bootstrap,
    you can use the created roles for day-to-day operations.

## Step 4: Verify the bootstrap

You can verify that the infrastructure was created by querying Snowflake:

```sql
SHOW DATABASES LIKE 'PUDO_MLOPS%';
SHOW SCHEMAS IN DATABASE PUDO_MLOPS;
SHOW ROLES LIKE 'PUDO%';
```

## What you have now

After completing this tutorial:

- [x] Local tooling installed (Python 3.10, uv, Git).
- [x] Snowflake connection configured via `.env` files.
- [x] Hub infrastructure deployed (databases, schemas, roles, warehouses).

## Next step

Continue to [Tutorial 2: Repo Mental Model](02-repo-mental-model.md) to
understand how the codebase is organised before you start deploying project
components.
