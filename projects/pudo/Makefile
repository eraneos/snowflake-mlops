# PUDO project verbs (per ADR-0012).
#
# Run from this directory or with `make -C projects/pudo <verb>`.

.PHONY: install \
        deploy-schema deploy-feature-store deploy-training-dag deploy-inference-dag \
        run-training-dag run-inference-dag \
        run-inference evaluate-predictions inference-alerts inference-summary \
        lint lint-fix format format-check quality clean

# ==================== Setup ====================

# Sync project dependencies
install:
	uv sync

# ==================== Deployment ====================

# Deploy project schema and stages (run this first).
deploy-schema:
	uv run python scripts/deploy_schema.py

# Deploy feature store
deploy-feature-store:
	uv run python scripts/deploy_feature_store.py

# Deploy training DAG
deploy-training-dag:
	uv run python scripts/deploy_training_dag.py

# Deploy inference DAG
deploy-inference-dag:
	uv run python scripts/deploy_inference_dag.py

# ==================== DAG Execution ====================

# Execute training DAG (without redeploying)
run-training-dag:
	uv run python scripts/run_training_dag.py

# Execute inference DAG (without redeploying)
run-inference-dag:
	uv run python scripts/run_inference_dag.py

# ==================== Inference Operations ====================

# Run inference on latest data
run-inference:
	uv run pudo-inference run

# Evaluate prediction accuracy
evaluate-predictions:
	uv run pudo-inference evaluate

# Show high-risk PUDO alerts
inference-alerts:
	uv run pudo-inference alerts

# Show inference metrics summary
inference-summary:
	uv run pudo-inference summary

# ==================== Code Quality ====================

# Lint with ruff
lint:
	uv run ruff check .

# Lint and fix automatically
lint-fix:
	uv run ruff check . --fix

# Format with ruff
format:
	uv run ruff format .

# Check formatting without changing files
format-check:
	uv run ruff format . --check

# Run lint + format check
quality: lint format-check

# Clean cache files
clean:
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/
