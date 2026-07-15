# Agent Core

`core/` is the global Brain of one agent. It owns the runtime package,
Explorer server, configuration, private stores, avatar assets, and core
utilities. Workspace consumers are local facades: they select one WoSP while
executing this agent's single core.

## Start here

- [Core documentation](documentation/README.md)
- [Architecture and ownership](documentation/architecture.md)
- [Documentation delivery policy](documentation/wiki-policy.md)
- [Brain subsystem](brain/documentation/README.md)
- [Brain Explorer subsystem](brain_explorer/documentation/README.md)

Create a consumer for an existing workspace:

```powershell
py core/core_cli.py create-brain <workspace-root> --json
```

After creation, invoke Brain only through the workspace facade:

```powershell
py '<workspace-root>/$agent/scripts/brain.py' help --json
```

`core_cli.py` is a consumer factory, not a normal Brain entrypoint.
