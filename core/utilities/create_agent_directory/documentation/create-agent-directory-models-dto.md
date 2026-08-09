# Create Agent Directory Models & DTOs

## Operation model

### `ChangeOperationStrategy`

Enumerates `COPY`, `REPLACE`, `MERGE`, `RENDER`, and `EXCLUDE`.

### `ChangeOperationDTO`

Frozen description of one root-scoped filesystem operation; it performs no I/O.

| Field | Type | Contract |
| --- | --- | --- |
| `source` | `Path` | Relative source; empty only for `RENDER`. |
| `target` | `Path` | Non-empty relative destination without traversal. |
| `strategy` | `ChangeOperationStrategy` | Selects executor behavior. |
| `ownership_root` | `Path` | Relative catalog root, default `Path(".")`. |
| `template` | `str \| None` | Required only for `RENDER`. |
| `remove_stale` | `bool` | Allows stale removal only for directory `COPY`. |

## Input DTOs

### `CreateAgentDirectoryInput`

`parent_path: Path`, `agent_name: str`, `user_name: str`.

### `UpdateAgentInput`

`target_root: Path`.

## Result DTOs

### `OperationResult`

`target: str`, `strategy: str`, `changed: bool`.

### `SynchronizationResult`

`operation_count`, `changed_count`, `unchanged_count`, and ordered `operations: tuple[OperationResult, ...]`.

### `CreateAgentDirectoryResult`

Normalized `agent_name`, trimmed `user_name`, `agent_root`, `staging_root`, ordered operations, and execution result.

### `UpdateAgentResult`

`source_root`, `target_root`, ordered operations, execution result, and non-excluded `updated_paths`.

## Invariants

DTOs reject absolute/traversal targets, invalid ownership roots, invalid templates, render sources, and unsafe exclusions. Every `EXCLUDE` must immediately follow a `COPY`, remain nested under that copy, and never remove stale destinations. MERGE recursively adds missing source keys while target values remain authoritative.
