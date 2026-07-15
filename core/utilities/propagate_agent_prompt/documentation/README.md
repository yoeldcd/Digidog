# Propagate Agent Prompt

Propagate Agent Prompt copies the canonical agent instruction file to every
configured mirror and verifies each copy by SHA-256.

## Ownership

- Source prompt: `<agent_dir>/AGENT.md`.
- Canonical agent directory: `agent_dir` in
  `core/configs/brain_configs.json`.
- Versioned mirror registry:
  `core/database/instruction_mirrors/agent_prompt_mirrors.txt`.

The utility belongs to one agent core. A consumer contributes only its local
workspace context and never owns the prompt registry.

## Consumer CLI

```powershell
py '$agent/scripts/brain.py' propagate-agent-prompt --json
py '$agent/scripts/brain.py' propagate-agent-prompt --dry-run --json
```

## Standalone CLI

```powershell
py core/utilities/propagate_agent_prompt/propagate_agent_prompt.py --json
py core/utilities/propagate_agent_prompt/propagate_agent_prompt.py --dry-run --json
```

Optional overrides are intended for maintenance and testing:

```powershell
py core/utilities/propagate_agent_prompt/propagate_agent_prompt.py `
  --source <AGENT.md> `
  --mirrors-file <registry.txt> `
  --json
```

## Registry contract

The registry contains one destination file per non-empty, non-comment line.
Destinations must be absolute paths and their parent directories must already
exist. An empty registry is valid for a newly created agent.

For each destination, the utility reports its path, status, whether it matches
the source, SHA-256 digest, and a diagnostic message. `--dry-run` performs no
writes and identifies copies that would change.

## Safety

The source is never modified. Each destination is copied byte-for-byte and
hashed after writing. Mirrors under protected user configuration directories
may require filesystem permission from the host environment.
