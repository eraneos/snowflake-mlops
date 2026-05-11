# Mock-data component verbs (per ADR-0012).
#
# Run from this directory or with `make -C mock_data <verb>`.

.PHONY: seed-shared-data \
        generate generate-test generate-local \
        inspect inspect-csv inspect-full peek \
        drop-database drop-database-force drop-tables reset-data \
        add-morning-data add-evening-data \
        simulation-status reset-simulation \
        test-connection

# Create the four PUDO source tables in SHARED_DATA and populate them.
# SHARED_DATA schema itself is owned by hub (`make -C hub deploy-infra`).
seed-shared-data:
	uv run python scripts/seed_shared_data.py

# Generate and upload data
generate:
	uv run pudo-generate generate

# Generate test data (no upload)
generate-test:
	uv run pudo-generate generate --test-mode --no-upload

# Generate without upload
generate-local:
	uv run pudo-generate generate --no-upload

# Inspect generated data (no upload)
inspect:
	uv run pudo-generate inspect --test-mode

# Inspect and save to CSV
inspect-csv:
	uv run pudo-generate inspect --test-mode --save-csv

# Inspect full dataset
inspect-full:
	uv run pudo-generate inspect --sample-rows 10

# Quick data peek
peek:
	uv run pudo-generate inspect --test-mode --sample-rows 3 --no-sample

# Drop entire database from Snowflake
drop-database:
	uv run pudo-generate drop-database

# Drop database without confirmation (dangerous!)
drop-database-force:
	uv run pudo-generate drop-database --confirm

# Drop all tables from Snowflake
drop-tables:
	uv run pudo-generate drop-tables

# Drop and recreate all tables (fresh start)
reset-data:
	uv run pudo-generate reset-data

# Generate morning data (parcels + delivery attempts)
add-morning-data:
	uv run pudo-generate add-day morning

# Generate evening data (ground truth occupancy)
add-evening-data:
	uv run pudo-generate add-day evening

# Show simulation status
simulation-status:
	uv run pudo-generate simulation-status

# Reset simulation (clear incremental data)
reset-simulation:
	uv run pudo-generate reset-simulation

# Test Snowflake connection
test-connection:
	uv run pudo-generate test-connection
