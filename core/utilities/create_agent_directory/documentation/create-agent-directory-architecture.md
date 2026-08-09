# Create Agent Directory Architecture

## Overview

The utility is rooted at `core/utilities/create_agent_directory/`. The root `create_agent_directory.py` is a minimal launcher delegating to `src/runtime/launcher.py`; typed DTOs and ports compose implementation under `src/`.

## Layers and dependency direction

### `src/domain/change_operation_dto.py`

Defines immutable strategies and validates path/template invariants without I/O.

### `src/application/create_agent/use_case.py`

Builds the ordered operation tuple, executes in staging, bootstraps lifecycle, publishes, and rolls back on failure.

### `src/application/update_agent/use_case.py`

Derives source from the owning agent root, builds synchronization operations, executes them, and runs target lifecycle.

### `src/application/synchronization/ports/executor_port.py`

Defines immutable `OperationResult` and `SynchronizationResult` contracts plus the executor protocol.

### `src/infrastructure/operation_executor.py`

Applies operations with containment checks, atomic writes, contiguous `EXCLUDE` metadata, and optional stale removal.

### `src/infrastructure/json_normalizer.py`

Recursively fills missing template keys while preserving target values; it never reads live source configuration.

### `src/adapters/cli/adapter.py`

Maps canonical and legacy CLI forms into typed inputs and JSON outcomes.

## Flows

### Creation

Build the sole ordered `tuple[ChangeOperationDTO, ...]`, execute against a temporary sibling, run lifecycle bootstrap, then publish with one rename; failures roll back staging.

### Update

Use the invoked agent root as source, execute explicit copy/replace/merge/render operations, then run target `init --json`.

## Authority boundaries

`AgentLayoutCatalog` and `SynchronizationCatalog` are not authorities. Application-built operation tuples are authoritative. Config files change only through explicit `MERGE` operations. Tests, caches, `node_modules`, and `documentation/wiki` are excluded through contiguous `EXCLUDE` operations.
