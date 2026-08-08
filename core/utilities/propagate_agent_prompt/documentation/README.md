<!-- Author: Yoel David <yoeldcd@gmail.com> | X: https://x.com/SAY6267 -->

# Propagate Agent Prompt

Propagate Agent Prompt copies the canonical agent instruction file to every
configured mirror and verifies each copy by SHA-256.

## Ownership

- Source template: `core/AGENTS.md`.
- Canonical agent directory: `agent_dir` in
  `core/configs/brain_configs.json`.
- Versioned mirror registry:
  `core/database/instruction_mirrors/agent_prompt_mirrors.txt`.
- Direct Brain consumer registry: `core/configs/brain_mirrors.json`; every
  registered repository receives an `AGENTS.md` at its root.

The utility belongs to one agent core. A consumer contributes its local
workspace root and never owns the prompt registry or canonical template.

## Template localization

The canonical template supports `{BRAIN_HOME}`, `{WORKSPACE_ROOT}`,
`{AGENT_HOME}`, `{BRAIN_SCRIPT_DIR}`, and `{LOCAL_BRAIN_SCRIPT}`.
`BRAIN_SCRIPT_DIR` identifies the launcher directory;
`LOCAL_BRAIN_SCRIPT` identifies the complete path including `brain.py`.
Propagation resolves every variable before writing:

- Direct Brain consumers receive absolute POSIX paths localized to their
  registered repository root.
- Generic mirrors receive paths relative to the active workspace: `core`, `.`,
  `.`, `$agent/scripts`, and `$agent/scripts/brain.py`, respectively.

Propagation fails before writing a destination if a supported variable cannot
be resolved. The canonical template itself is never modified.

Executable expressions ending in `brain.py` or `core_cli.py` remain unquoted in
the canonical template. The renderer wraps their complete localized paths in
PowerShell single quotes and escapes embedded apostrophes, so quoting belongs to
the output contract rather than to template wording.

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
  --source <AGENTS.md> `
  --mirrors-file <registry.txt> `
  --consumers-file <brain_mirrors.json> `
  --json
```

## Registry contract

The explicit mirror registry contains one destination file per non-empty,
non-comment line. The consumer registry contributes each registered repository
root as an additional `<repository>/AGENTS.md` destination.
Destinations must be absolute paths and their parent directories must already
exist. Duplicate destinations and the canonical source itself are ignored.

For each destination, the utility reports its path, status, whether it matches
the source, SHA-256 digest, and a diagnostic message. `--dry-run` performs no
writes and identifies copies that would change.

## Safety

The source is never modified. Each destination receives its rendered UTF-8
content and is hashed after writing. Mirrors under protected user configuration
directories may require filesystem permission from the host environment.
