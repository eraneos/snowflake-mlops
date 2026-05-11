# Local Setup & Env Files

This guide explains how to configure your local environment for working with
the repository.

## The `.env` file pattern

Each component reads Snowflake connection settings from a `.env` file in its
own directory:

```
hub/.env
mock_data/.env
projects/pudo/.env
```

## Required variables

| Variable | Description |
|---|---|
| `SNOWFLAKE_ACCOUNT` | Your Snowflake account identifier (e.g., `org-account`). |
| `SNOWFLAKE_USER` | Your Snowflake username. |
| `SNOWFLAKE_ROLE` | The role to assume (changes per environment). |
| `SNOWFLAKE_WAREHOUSE` | The warehouse to use for queries. |

## Creating the hub `.env`

Start with the hub, since it is the first component you deploy:

```bash
cat > hub/.env << 'EOF'
SNOWFLAKE_ACCOUNT=my-org-my-account
SNOWFLAKE_USER=my-username
SNOWFLAKE_ROLE=ACCOUNTADMIN
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
EOF
```

!!! warning "ACCOUNTADMIN for bootstrap only"
    Use `ACCOUNTADMIN` only for the initial hub bootstrap. After bootstrap,
    switch to the created operational role (e.g., `PUDO_DEV_ROLE`).

## Symlinking `.env` files

If you use the same credentials across components, symlink them:

```bash
cd mock_data && ln -s ../hub/.env .env
cd projects/pudo && ln -s ../../hub/.env .env
```

This way you only need to update one file when credentials change.

## Environment-specific roles

After hub bootstrap, use the environment-specific roles:

| Environment | Role |
|---|---|
| DEV | `PUDO_DEV_ROLE` |
| STAGING | `PUDO_STAGING_ROLE` |
| PROD | `PUDO_PROD_ROLE` |

Update your `.env` to use the appropriate role for the branch you are working
on.

## Python environment

Each component manages its own Python environment via `uv`:

```bash
# Install dependencies for a component
cd hub && uv sync
cd mock_data && uv sync
cd projects/pudo && uv sync
```

You do not need to manually activate a virtual environment. `uv run` handles
this automatically.

## Verifying your setup

Test your connection from the hub:

```bash
cd hub
uv run python -c "
from snowflake.snowpark import Session
from hub.core.session import create_session
session = create_session()
print(session.sql('SELECT CURRENT_ROLE()').collect())
session.close()
"
```

If this prints your role, your `.env` is correctly configured.

## `.gitignore`

The `.env` files are excluded from Git via `.gitignore`. Never commit
credentials to the repository.
