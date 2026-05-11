# Concepts

Explanatory pages that cover the architecture, Snowflake ML lifecycle, and
design decisions behind this reference repository.

These pages explain **why** the repository is structured the way it is. For
step-by-step instructions, see the [Tutorials](../tutorials/index.md).

| Concept | What it explains |
|---|---|
| [Repo Layers & Ownership](repo-layers.md) | Hub-spoke architecture, component boundaries, and ownership rules. |
| [Snowflake ML Lifecycle](snowflake-ml-lifecycle.md) | The end-to-end ML lifecycle on Snowflake: features, training, inference, evaluation, retraining. |
| [Feature Store](feature-store.md) | Entities, feature views, point-in-time correctness, versioning, and namespacing. |
| [Model Registry & Training Artifacts](model-registry-and-training-artifacts.md) | Model registration, versioning, metrics, and artifact management. |
| [Task Graphs & Orchestration](task-graphs-and-orchestration.md) | Snowflake task graphs, DAG structure, scheduling, and the deploy-vs-run pattern. |
| [Environments & Promotion](environments-and-promotion.md) | Environment topology, schema layout, configuration overlays, and promotion mechanics. |
