# mock_data

Sibling component that populates `SHARED_DATA` with synthetic source tables (per ADR-0005).

In a real deployment `SHARED_DATA` is filled by upstream ingestion. In this open-source repo it is filled by the generators in this component so the end-to-end flow runs without external systems. Mock data is the only writer of `SHARED_DATA`; projects only read.

The baseline mock data is PUDO-domain (parcel pick-up / drop-off), matching the example project under `projects/pudo/`. The Python package is named `pudo_data` because the data IS PUDO-domain at baseline; the component directory is named `mock_data` because the role of the directory is "mock data, replaced by real ingestion in production" (per ADR-0005).

## Layout

- `src/pudo_data/generators/` — synthetic data generators.
- `src/pudo_data/core/` — minimal session, credentials, env detection, sql helpers (per ADR-0001/ADR-0005; duplicated from hub side at baseline, candidate for centralization once ADR-0020 lands).
- `src/pudo_data/config_models.py` — Pydantic config models, co-located rather than in a sub-package since mock_data is small enough to skip block subdivision (per ADR-0005).
- `config/` — layered YAML config (sibling of `src/`, follows the same pattern as projects per ADR-0003).
- `scripts/seed_shared_data.py` — creates the four source tables and seeds them by invoking `pudo-generate generate`.
- `scripts/sql/tables/pudo_tables.sql` — DDL for the four source tables.
- `Makefile` — verb wrappers around `scripts/` (per ADR-0012).

## CLI

`pudo-generate` is registered as a console script in `pyproject.toml` (CLI verbs follow the mock data's domain per ADR-0005).

## Deploy

`SHARED_DATA` itself is created by hub. Run hub first, then seed:

```sh
make -C hub deploy-infra
make -C mock_data seed-shared-data
```
